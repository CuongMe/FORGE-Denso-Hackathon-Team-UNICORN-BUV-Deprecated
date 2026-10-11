"""Persistent evaluation runs and query telemetry; no evaluator provider required."""

from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import unicodedata
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)
DATA_ROOT = Path(__file__).resolve().parents[3] / 'data' / 'evaluation'
DATASETS = {'abstention': 'abstention_holdout_v1.jsonl'}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cases(dataset: str) -> list[dict]:
    return [json.loads(line) for line in (DATA_ROOT / DATASETS[dataset]).read_text(encoding='utf-8').splitlines() if line.strip()]


def tokens(text: str) -> Counter:
    normalized = unicodedata.normalize('NFKC', text).casefold()
    # Split CJK characters to compare sentences without whitespace.
    normalized = re.sub(r'([\u3040-\u30ff\u3400-\u9fff])', r' \1 ', normalized)
    return Counter(re.findall(r'[^\W_]+', normalized))


def token_f1(answer: str, reference: str) -> float:
    actual, expected = tokens(answer), tokens(reference)
    denominator = sum(actual.values()) + sum(expected.values())
    return 2 * sum((actual & expected).values()) / denominator if denominator else 0.0


def evidence_matches(item, evidence: dict) -> bool:
    # Golden Qxxx annotation IDs are not live Docling chunk IDs: score source/page.
    pages = set(item.pages) | ({item.page} if item.page is not None else set())
    return item.doc_id == evidence['doc_id'] and (evidence.get('page') is None or evidence['page'] in pages)


def score_case(case: dict, response: QueryResponse) -> dict:
    gold = case['gold_evidence']
    candidates = response.trace.candidates
    hybrid = sorted(candidates, key=lambda item: item.hybrid_rank)
    ranked = sorted((item for item in candidates if item.rerank_rank is not None), key=lambda item: item.rerank_rank)

    def reciprocal_rank(items):
        return next((1 / rank for rank, item in enumerate(items, 1)
                     if any(evidence_matches(item, evidence) for evidence in gold)), 0.0)

    predicted = not response.abstained and response.grounding != 'no_match'
    actual_tokens = tokens(response.answer)
    return {
        'answerability_correct': predicted == case['answerable'], 'predicted_answerable': predicted,
        'source_recall': sum(any(evidence_matches(item, e) for item in ranked) for e in gold) / len(gold) if gold else None,
        'source_precision': sum(any(evidence_matches(item, e) for e in gold) for item in ranked) / len(ranked) if gold and ranked else (0.0 if gold else None),
        'hybrid_mrr': reciprocal_rank(hybrid[:len(ranked)]) if gold else None,
        'reranked_mrr': reciprocal_rank(ranked) if gold else None,
        'citation_precision': sum(any(evidence_matches(item, e) for e in gold) for item in response.citations) / len(response.citations) if gold and response.citations else (0.0 if gold else None),
        'answer_token_f1': token_f1(response.answer, case['reference_answer']) if case['answerable'] else None,
        'required_fact_coverage': sum(sum((tokens(fact) & actual_tokens).values()) / max(1, sum(tokens(fact).values())) for fact in case['required_facts']) / len(case['required_facts']) if case['required_facts'] else None,
    }


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summarize(results: list[dict]) -> dict:
    successful = [item for item in results if item['status'] == 'completed']
    metrics = {}
    for name in ('source_recall', 'source_precision', 'hybrid_mrr', 'reranked_mrr', 'citation_precision', 'answer_token_f1', 'required_fact_coverage', 'answerability_correct'):
        values = [item['scores'][name] for item in successful if item['scores'][name] is not None]
        metrics[name] = sum(values) / len(values) if values else None
    metrics['reranker_lift'] = metrics['reranked_mrr'] - metrics['hybrid_mrr'] if metrics['hybrid_mrr'] is not None else None
    tp = sum(item['answerable'] and item['scores']['predicted_answerable'] for item in successful)
    fp = sum(not item['answerable'] and item['scores']['predicted_answerable'] for item in successful)
    fn = sum(item['answerable'] and not item['scores']['predicted_answerable'] for item in successful)
    metrics['answerability_f1'] = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {**metrics, 'completed': len(successful), 'failed': len(results) - len(successful),
            'p50_latency_ms': percentile([item['latency_ms'] for item in successful], .5),
            'p95_latency_ms': percentile([item['latency_ms'] for item in successful], .95)}


class EvaluationStore:
    def __init__(self, database: str, *, retention_days: int | None = None):
        self.database = database
        configured_retention = retention_days
        if configured_retention is None:
            configured_retention = int(os.getenv('FORGE_METRICS_RETENTION_DAYS', '30'))
        self.retention_days = max(1, configured_retention)

    def connect(self):
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with closing(self.connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS single_active_evaluation
                    ON evaluation_runs(status) WHERE status = 'running';
                CREATE TABLE IF NOT EXISTS query_metrics (
                    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, latency_ms REAL NOT NULL,
                    succeeded INTEGER NOT NULL, abstained INTEGER NOT NULL, citations INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_jobs (
                    run_id TEXT PRIMARY KEY, status TEXT NOT NULL, cases TEXT NOT NULL,
                    worker_id TEXT, lease_expires_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(run_id) REFERENCES evaluation_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS evaluation_jobs_status
                    ON evaluation_jobs(status, lease_expires_at);
                CREATE INDEX IF NOT EXISTS query_metrics_created_at
                    ON query_metrics(created_at);
            ''')
            columns = {
                row['name']
                for row in db.execute('PRAGMA table_info(query_metrics)').fetchall()
            }
            for name, definition in {
                'prompt_tokens': 'INTEGER NOT NULL DEFAULT 0',
                'completion_tokens': 'INTEGER NOT NULL DEFAULT 0',
                'total_tokens': 'INTEGER NOT NULL DEFAULT 0',
                'estimated_cost_usd': 'REAL NOT NULL DEFAULT 0',
            }.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE query_metrics ADD COLUMN {name} {definition}')

    def save(self, run: dict):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE evaluation_runs SET status=?, payload=? WHERE run_id=?', (run['status'], json.dumps(run, ensure_ascii=False), run['run_id']))

    def get(self, run_id: str) -> dict | None:
        with closing(self.connect()) as db:
            row = db.execute('SELECT payload FROM evaluation_runs WHERE run_id=?', (run_id,)).fetchone()
        return json.loads(row['payload']) if row else None

    def runs(self) -> list[dict]:
        with closing(self.connect()) as db:
            rows = db.execute('SELECT payload FROM evaluation_runs ORDER BY rowid DESC LIMIT 50').fetchall()
        return [{key: value for key, value in json.loads(row['payload']).items() if key != 'results'} for row in rows]

    def enqueue(self, run: dict, cases: list[dict]) -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                'INSERT INTO evaluation_runs VALUES (?, ?, ?)',
                (run['run_id'], run['status'], json.dumps(run, ensure_ascii=False)),
            )
            db.execute(
                'INSERT INTO evaluation_jobs(run_id, status, cases) VALUES (?, ?, ?)',
                (run['run_id'], 'queued', json.dumps(cases, ensure_ascii=False)),
            )

    def claim_next(self, worker_id: str, *, lease_seconds: float = 120) -> tuple[dict, list[dict]] | None:
        claimed_at = now()
        lease_expires = (
            datetime.now(timezone.utc) + timedelta(seconds=max(0, lease_seconds))
        ).isoformat()
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute(
                "SELECT 1 FROM evaluation_jobs WHERE status='running' AND lease_expires_at > ? LIMIT 1",
                (claimed_at,),
            ).fetchone()
            if active is not None:
                db.rollback()
                return None
            row = db.execute(
                """
                SELECT jobs.run_id, jobs.cases, runs.payload
                FROM evaluation_jobs jobs
                JOIN evaluation_runs runs ON runs.run_id = jobs.run_id
                WHERE jobs.status='queued'
                   OR (jobs.status='running' AND jobs.lease_expires_at <= ?)
                ORDER BY CASE jobs.status WHEN 'running' THEN 0 ELSE 1 END, jobs.rowid
                LIMIT 1
                """,
                (claimed_at,),
            ).fetchone()
            if row is None:
                db.rollback()
                return None
            run = json.loads(row['payload'])
            run['status'] = 'running'
            run['started_at'] = run.get('started_at') or claimed_at
            db.execute(
                """
                UPDATE evaluation_jobs
                SET status='running', worker_id=?, lease_expires_at=?, attempts=attempts+1
                WHERE run_id=?
                """,
                (worker_id, lease_expires, row['run_id']),
            )
            db.execute(
                'UPDATE evaluation_runs SET status=?, payload=? WHERE run_id=?',
                ('running', json.dumps(run, ensure_ascii=False), row['run_id']),
            )
            db.commit()
        return run, json.loads(row['cases'])

    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: float = 120) -> None:
        lease_expires = (
            datetime.now(timezone.utc) + timedelta(seconds=max(0, lease_seconds))
        ).isoformat()
        with closing(self.connect()) as db, db:
            cursor = db.execute(
                """
                UPDATE evaluation_jobs SET lease_expires_at=?
                WHERE run_id=? AND status='running' AND worker_id=?
                """,
                (lease_expires, run_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError('Evaluation lease is no longer owned by this worker.')

    def finish(self, run: dict, worker_id: str) -> None:
        with closing(self.connect()) as db, db:
            cursor = db.execute(
                """
                UPDATE evaluation_jobs
                SET status='completed', worker_id=NULL, lease_expires_at=NULL
                WHERE run_id=? AND worker_id=?
                """,
                (run['run_id'], worker_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError('Evaluation lease is no longer owned by this worker.')
            db.execute(
                'UPDATE evaluation_runs SET status=?, payload=? WHERE run_id=?',
                (run['status'], json.dumps(run, ensure_ascii=False), run['run_id']),
            )

    def record_query(self, latency_ms: float, response: QueryResponse | None):
        with closing(self.connect()) as db, db:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
            db.execute('DELETE FROM query_metrics WHERE created_at < ?', (cutoff,))
            usage = response.usage if response else None
            db.execute(
                """
                INSERT INTO query_metrics(
                    created_at, latency_ms, succeeded, abstained, citations,
                    prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now(),
                    latency_ms,
                    response is not None,
                    bool(response and (response.abstained or response.grounding == 'no_match')),
                    len(response.citations) if response else 0,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                    usage.total_tokens if usage else 0,
                    usage.estimated_cost_usd if usage else 0,
                ),
            )

    def metrics(self) -> dict:
        with closing(self.connect()) as db:
            total = db.execute('SELECT COUNT(*) FROM query_metrics').fetchone()[0]
            rows = db.execute('SELECT * FROM query_metrics ORDER BY id DESC LIMIT 1000').fetchall()
        success = [row for row in rows if row['succeeded']]
        return {'total_queries': total, 'window_size': len(rows), 'retention_days': self.retention_days,
                'success_rate': len(success) / len(rows) if rows else None,
                'abstention_rate': sum(row['abstained'] for row in success) / len(success) if success else None,
                'p50_latency_ms': percentile([row['latency_ms'] for row in rows], .5),
                'p95_latency_ms': percentile([row['latency_ms'] for row in rows], .95),
                'citation_rate': sum(row['citations'] > 0 for row in success) / len(success) if success else None,
                'prompt_tokens': sum(row['prompt_tokens'] for row in rows),
                'completion_tokens': sum(row['completion_tokens'] for row in rows),
                'total_tokens': sum(row['total_tokens'] for row in rows),
                'estimated_cost_usd': sum(row['estimated_cost_usd'] for row in rows),
                'recent': [dict(row) for row in rows[:100]]}


class EvaluationRequest(BaseModel):
    dataset: Literal['abstention'] = 'abstention'
    limit: int = Field(default=4, ge=1, le=4)


def execute_run(store: EvaluationStore, run: dict, cases: list[dict], execute, worker_id: str):
    try:
        for case in cases:
            started = time.perf_counter()
            result = {key: case[key] for key in ('case_id', 'question', 'reference_answer', 'required_facts', 'gold_evidence', 'answerable', 'question_type', 'language', 'verification_status')}
            try:
                response = execute(QueryRequest(question=case['question']))
                result.update(status='completed', response=response.model_dump(mode='json'), scores=score_case(case, response), error=None)
            except Exception:
                logger.exception('Evaluation case failed: %s', case['case_id'])
                result.update(status='failed', response=None, scores=None, error='Query execution failed. Check API/provider availability and service logs.')
            result['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
            run['results'].append(result)
            run['summary'] = summarize(run['results'])
            store.save(run)
            store.renew_lease(run['run_id'], worker_id)
        run['status'] = 'completed' if not run['summary']['failed'] else 'completed_with_errors'
    except Exception:
        logger.exception('Evaluation run failed: %s', run['run_id'])
        run['status'] = 'failed'
    finally:
        run['finished_at'] = now()
        store.finish(run, worker_id)


class EvaluationWorker:
    def __init__(self, store: EvaluationStore, execute, *, poll_interval: float = .5) -> None:
        self.store = store
        self.execute = execute
        self.poll_interval = max(.05, poll_interval)
        self.worker_id = 'evaluation-worker-' + uuid4().hex
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> bool:
        claimed = self.store.claim_next(self.worker_id)
        if claimed is None:
            return False
        run, cases = claimed
        execute_run(self.store, run, cases, self.execute, self.worker_id)
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self.run_once():
                self._stop_event.wait(self.poll_interval)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name='forge-evaluation-worker',
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval * 4))
            self._thread = None


def evaluation_router(get_store, execute, configuration, authorize=None) -> APIRouter:
    dependencies = [Depends(authorize)] if authorize is not None else []
    router = APIRouter(prefix='/api', dependencies=dependencies)

    @router.get('/metrics')
    def metrics():
        return get_store().metrics()

    @router.get('/evaluations/datasets')
    def datasets():
        cases = load_cases('abstention')
        return {'data': [{'id': 'abstention', 'count': len(cases), 'answerable': sum(case['answerable'] for case in cases)}]}

    @router.get('/evaluations')
    def runs():
        return {'data': get_store().runs()}

    @router.get('/evaluations/{run_id}')
    def detail(run_id: str):
        run = get_store().get(run_id)
        if run is None:
            raise HTTPException(404, detail={'code': 'EVALUATION_NOT_FOUND', 'message': 'Evaluation run not found.'})
        return run

    @router.post('/evaluations', status_code=202)
    def start(payload: EvaluationRequest):
        store = get_store()
        cases = load_cases(payload.dataset)
        cases = cases[:payload.limit]
        run = {'run_id': 'eval-' + uuid4().hex[:16], 'status': 'queued', 'dataset': payload.dataset,
               'total': len(cases), 'queued_at': now(), 'started_at': None, 'finished_at': None,
               'dataset_hash': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
               'configuration': configuration(), 'results': [], 'summary': summarize([])}
        try:
            store.enqueue(run, cases)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, detail={'code': 'EVALUATION_RUNNING', 'message': 'An evaluation is already running.'}) from exc
        return run

    return router
