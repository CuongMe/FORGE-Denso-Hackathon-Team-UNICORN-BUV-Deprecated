from concurrent.futures import ThreadPoolExecutor
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.evaluation import EvaluationStore, EvaluationWorker, evaluation_router, load_cases, score_case, summarize, token_f1
from app.models import Citation, QueryResponse, RetrievalCandidate, RetrievalTrace, TokenUsage


def response(*, abstained=False):
    return QueryResponse(answer='9.5 ± 0.5 N·m', abstained=abstained,
        grounding='grounded', citations=[Citation(chunk_id='live:chunk-1', doc_id='WI-ASSY-001',
            source_name='manual.pdf', page=1, region='spec', quote='9.5 ± 0.5 N·m', score=.9)],
        trace=RetrievalTrace(candidates_considered=2, reranked_count=2, reranker='test',
            evidence_threshold=.45, latency_ms=20, candidates=[
                RetrievalCandidate(hybrid_rank=1, rerank_rank=2, chunk_id='wrong', doc_id='OTHER', source_name='other.pdf', page=1, hybrid_score=.8),
                RetrievalCandidate(hybrid_rank=2, rerank_rank=1, chunk_id='live:chunk-1', doc_id='WI-ASSY-001', source_name='manual.pdf', pages=(1,), hybrid_score=.7),
            ]))


def test_scoring_uses_source_page_and_honest_lexical_proxy():
    case = load_cases('golden')[0]
    scores = score_case(case, response())
    assert scores['source_recall'] == 1
    assert scores['source_precision'] == .5
    assert scores['hybrid_mrr'] == .5
    assert scores['reranked_mrr'] == 1
    assert scores['citation_precision'] == 1
    assert scores['answer_token_f1'] == 1
    assert scores['answerability_correct'] is True
    wrong_page = response()
    wrong_page.trace.candidates[1].pages = (2,)
    assert score_case(case, wrong_page)['source_recall'] == 0
    assert token_f1('red red', 'red') == pytest.approx(2 / 3)
    assert token_f1('', '') == 0
    assert token_f1('作業停止', '停止') == pytest.approx(2 / 3)


def test_abstention_and_empty_metrics_are_not_invented():
    case = load_cases('abstention')[0]
    assert score_case(case, response())['answerability_correct'] is False
    scores = score_case(case, response(abstained=True))
    assert scores['answerability_correct'] is True
    assert scores['source_recall'] is None
    assert scores['answer_token_f1'] is None
    assert summarize([])['p95_latency_ms'] is None
    assert summarize([])['answerability_correct'] is None


def test_routes_persist_runs_failures_and_exportable_details(tmp_path):
    store = EvaluationStore(str(tmp_path / 'evaluation.sqlite3'))
    store.initialize()
    calls = []

    def execute(payload):
        calls.append(payload.question)
        if len(calls) == 2:
            raise RuntimeError('private provider error')
        return response()

    app = FastAPI()
    app.include_router(evaluation_router(lambda: store, execute, lambda: {'model': 'test'}))
    with TestClient(app) as client:
        assert client.get('/api/metrics').json()['total_queries'] == 0
        mixed = client.get('/api/evaluations/datasets').json()['data'][2]
        assert mixed['count'] == 34
        assert mixed['signed_off'] == 0
        assert mixed['pending_review'] == 34
        assert client.post('/api/evaluations', json={'dataset': '../secret', 'limit': 2}).status_code == 422
        assert client.post('/api/evaluations', json={'limit': 35}).status_code == 422
        started = client.post('/api/evaluations', json={'dataset': 'all', 'limit': 2})
        assert started.status_code == 202
        assert started.json()['status'] == 'queued'
        assert EvaluationWorker(store, execute, poll_interval=.01).run_once() is True
        detail = client.get('/api/evaluations/' + started.json()['run_id']).json()
        assert detail['status'] == 'completed_with_errors'
        assert detail['summary']['completed'] == detail['summary']['failed'] == 1
        assert detail['results'][1]['answerable'] is False
        assert 'private' not in detail['results'][1]['error']
        assert detail['configuration'] == {'model': 'test'}
        assert len(detail['dataset_hash']) == 64
        assert 'results' not in client.get('/api/evaluations').json()['data'][0]
        assert client.get('/api/evaluations/missing').status_code == 404
        assert client.get('/api/metrics').json()['total_queries'] == 0
    reopened = EvaluationStore(store.database)
    assert reopened.get(detail['run_id'])['results'] == detail['results']


def test_durable_queue_uses_exclusive_leases_and_recovers_expired_work(tmp_path):
    store = EvaluationStore(str(tmp_path / 'evaluation.sqlite3'))
    store.initialize()
    run = {
        'run_id': 'one',
        'status': 'queued',
        'dataset': 'golden',
        'total': 1,
        'queued_at': '2026-01-01T00:00:00+00:00',
        'started_at': None,
        'finished_at': None,
        'results': [],
        'summary': summarize([]),
    }
    store.enqueue(run, load_cases('golden')[:1])

    claimed = store.claim_next('worker-a', lease_seconds=60)
    assert claimed is not None
    assert claimed[0]['status'] == 'running'
    assert store.claim_next('worker-b', lease_seconds=60) is None

    store.renew_lease('one', 'worker-a', lease_seconds=0)
    recovered = EvaluationStore(store.database)
    recovered.initialize()
    reclaimed = recovered.claim_next('worker-b', lease_seconds=60)
    assert reclaimed is not None
    assert reclaimed[0]['run_id'] == 'one'
    assert reclaimed[0]['started_at'] == claimed[0]['started_at']


def test_query_metrics_are_thread_safe_and_include_failures(tmp_path):
    store = EvaluationStore(str(tmp_path / 'evaluation.sqlite3'), retention_days=1)
    store.initialize()
    assert store.metrics()['success_rate'] is None
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: store.record_query(100, response()), range(10)))
    store.record_query(500, None)
    metered = response(abstained=True)
    metered.usage = TokenUsage(
        prompt_tokens=120,
        completion_tokens=14,
        total_tokens=134,
        estimated_cost_usd=.001,
    )
    with store.connect() as db, db:
        db.execute(
            'INSERT INTO query_metrics(created_at, latency_ms, succeeded, abstained, citations) VALUES (?, ?, ?, ?, ?)',
            ('2020-01-01T00:00:00+00:00', 1, 1, 0, 0),
        )
    store.record_query(200, metered)
    metrics = store.metrics()
    assert metrics['total_queries'] == 12
    assert metrics['success_rate'] == pytest.approx(11 / 12)
    assert metrics['p95_latency_ms'] == 500
    assert metrics['abstention_rate'] == pytest.approx(1 / 11)
    assert metrics['total_tokens'] == 134
    assert metrics['estimated_cost_usd'] == pytest.approx(.001)
    assert metrics['retention_days'] == 1
    assert all('question' not in row for row in metrics['recent'])
