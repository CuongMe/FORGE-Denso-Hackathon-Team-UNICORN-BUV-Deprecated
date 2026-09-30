from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping
from uuid import uuid4

from app.pipeline import INGESTION_STAGE_DEFINITIONS, INGESTION_STAGE_LABELS, StageStatus


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATE_DB_PATH = PROJECT_ROOT / 'data' / '.forge-state' / 'forge.sqlite3'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _loads(value: str | None, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class LifecycleStore:
    """Small durable store for document, job, review, and index state."""

    def __init__(self, database: Path | str | None = None) -> None:
        configured = database or os.getenv('FORGE_STATE_DB_PATH') or DEFAULT_STATE_DB_PATH
        self.database = str(configured)

    def _connect(self) -> sqlite3.Connection:
        if self.database != ':memory:':
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA busy_timeout = 30000')
        if self.database != ':memory:':
            connection.execute('PRAGMA journal_mode = WAL')
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    language TEXT NOT NULL,
                    factory_topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    sheet_count INTEGER NOT NULL DEFAULT 0,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    column_count INTEGER NOT NULL DEFAULT 0,
                    image_count INTEGER NOT NULL DEFAULT 0,
                    region_types TEXT NOT NULL DEFAULT '[]',
                    content_hash TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    ingestion_job_id TEXT,
                    error TEXT,
                    index_version TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
                    source_path TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    result TEXT,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
                    ON ingestion_jobs(status, queued_at);
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_document
                    ON ingestion_jobs(doc_id, updated_at);

                CREATE TABLE IF NOT EXISTS ingestion_stages (
                    job_id TEXT NOT NULL REFERENCES ingestion_jobs(job_id) ON DELETE CASCADE,
                    stage TEXT NOT NULL,
                    stage_order INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, stage)
                );

                CREATE INDEX IF NOT EXISTS idx_ingestion_stages_job_order
                    ON ingestion_stages(job_id, stage_order);

                CREATE TABLE IF NOT EXISTS review_items (
                    review_id TEXT PRIMARY KEY,
                    job_id TEXT REFERENCES ingestion_jobs(job_id),
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
                    chunk_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    page INTEGER,
                    bbox TEXT,
                    confidence REAL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_review_items_status
                    ON review_items(status, updated_at);

                CREATE TABLE IF NOT EXISTS index_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    collection_name TEXT NOT NULL,
                    corpus_version TEXT NOT NULL,
                    indexed_documents INTEGER NOT NULL,
                    indexed_chunks INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_key TEXT PRIMARY KEY,
                    corpus_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_query_cache_expiry
                    ON query_cache(expires_at);
                '''
            )
        finally:
            connection.close()

    @staticmethod
    def _document(
        row: sqlite3.Row | None,
        *,
        include_internal: bool = True,
    ) -> dict[str, object] | None:
        if row is None:
            return None
        document = {
            'doc_id': row['doc_id'],
            'source_name': row['source_name'],
            'source_path': row['source_path'],
            'format': row['file_format'],
            'modality': row['modality'],
            'language': row['language'],
            'factory_topic': row['factory_topic'],
            'status': row['status'],
            'chunk_count': row['chunk_count'],
            'page_count': row['page_count'],
            'sheet_count': row['sheet_count'],
            'row_count': row['row_count'],
            'column_count': row['column_count'],
            'image_count': row['image_count'],
            'region_types': _loads(row['region_types'], []),
        }
        if include_internal:
            document.update({
                'content_hash': row['content_hash'],
                'size_bytes': row['size_bytes'],
                'ingestion_job_id': row['ingestion_job_id'],
                'error': row['error'],
                'index_version': row['index_version'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })
        return document

    @staticmethod
    def _job(row: sqlite3.Row | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            'job_id': row['job_id'],
            'document_id': row['doc_id'],
            'source_path': row['source_path'],
            'original_filename': row['original_filename'],
            'content_hash': row['content_hash'],
            'idempotency_key': row['idempotency_key'],
            'status': row['status'],
            'stage': row['stage'],
            'attempts': row['attempts'],
            'error': row['error'],
            'result': _loads(row['result'], None),
            'queued_at': row['queued_at'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'updated_at': row['updated_at'],
        }

    @staticmethod
    def _stage(row: sqlite3.Row) -> dict[str, object]:
        return {
            'stage': row['stage'],
            'label': row['label'],
            'status': row['status'],
            'progress': row['progress'],
            'message': row['message'],
            'error': row['error'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'updated_at': row['updated_at'],
        }

    @staticmethod
    def _seed_job_stages(connection: sqlite3.Connection, job_id: str) -> None:
        now = _now()
        for order, (stage, label) in enumerate(INGESTION_STAGE_DEFINITIONS):
            is_queued = stage == 'queued'
            connection.execute(
                '''
                INSERT OR IGNORE INTO ingestion_stages (
                    job_id, stage, stage_order, label, status, progress, message,
                    started_at, completed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    job_id,
                    stage,
                    order,
                    label,
                    'completed' if is_queued else 'pending',
                    100 if is_queued else 0,
                    'Job accepted and waiting for a worker.' if is_queued else '',
                    now if is_queued else None,
                    now if is_queued else None,
                    now,
                ),
            )

    def get_job_stages(self, job_id: str) -> list[dict[str, object]]:
        self.initialize()
        connection = self._connect()
        try:
            job = connection.execute(
                'SELECT status, stage, error, updated_at FROM ingestion_jobs WHERE job_id = ?',
                (job_id,),
            ).fetchone()
            if job is None:
                return []
            self._seed_job_stages(connection, job_id)
            rows = connection.execute(
                'SELECT * FROM ingestion_stages WHERE job_id = ? ORDER BY stage_order',
                (job_id,),
            ).fetchall()
            stages = [self._stage(row) for row in rows]
            if job['status'] == 'failed':
                stages.append(
                    {
                        'stage': 'failed',
                        'label': 'Failed',
                        'status': 'failed',
                        'progress': 100,
                        'message': 'Ingestion failed.',
                        'error': job['error'],
                        'started_at': job['updated_at'],
                        'completed_at': job['updated_at'],
                        'updated_at': job['updated_at'],
                    }
                )
            return stages
        finally:
            connection.close()

    def update_stage(
        self,
        job_id: str,
        stage: str,
        *,
        status: StageStatus,
        progress: int,
        message: str,
        error: str | None = None,
    ) -> dict[str, object]:
        if stage not in INGESTION_STAGE_LABELS:
            raise ValueError(f'Unknown ingestion stage: {stage}')
        if status not in {'pending', 'started', 'completed', 'failed'}:
            raise ValueError(f'Unknown ingestion stage status: {status}')
        self.initialize()
        now = _now()
        bounded_progress = min(100, max(0, int(progress)))
        connection = self._connect()
        try:
            self._seed_job_stages(connection, job_id)
            existing = connection.execute(
                'SELECT started_at, completed_at FROM ingestion_stages WHERE job_id = ? AND stage = ?',
                (job_id, stage),
            ).fetchone()
            if existing is None:
                raise KeyError(f'Unknown ingestion job: {job_id}')
            started_at = existing['started_at'] or (now if status in {'started', 'completed', 'failed'} else None)
            completed_at = now if status in {'completed', 'failed'} else existing['completed_at']
            connection.execute(
                '''
                UPDATE ingestion_stages
                SET status = ?, progress = ?, message = ?, error = ?,
                    started_at = ?, completed_at = ?, updated_at = ?
                WHERE job_id = ? AND stage = ?
                ''',
                (
                    status,
                    bounded_progress,
                    message,
                    error,
                    started_at,
                    completed_at,
                    now,
                    job_id,
                    stage,
                ),
            )
            connection.execute(
                'UPDATE ingestion_jobs SET stage = ?, updated_at = ? WHERE job_id = ?',
                (stage, now, job_id),
            )
            row = connection.execute(
                'SELECT * FROM ingestion_stages WHERE job_id = ? AND stage = ?',
                (job_id, stage),
            ).fetchone()
            assert row is not None
            return self._stage(row)
        finally:
            connection.close()

    def upsert_document(
        self,
        summary: Mapping[str, object],
        *,
        content_hash: str = '',
        size_bytes: int = 0,
        status: str | None = None,
        ingestion_job_id: str | None = None,
        error: str | None = None,
        index_version: str = '',
    ) -> dict[str, object]:
        self.initialize()
        now = _now()
        document_status = status or str(summary.get('status') or 'registered')
        values = {
            'doc_id': str(summary['doc_id']),
            'source_name': str(summary.get('source_name') or ''),
            'source_path': str(summary.get('source_path') or ''),
            'file_format': str(summary.get('format') or 'DOCUMENT').upper(),
            'modality': str(summary.get('modality') or 'document'),
            'language': str(summary.get('language') or 'multilingual'),
            'factory_topic': str(summary.get('factory_topic') or 'factory source'),
            'status': document_status,
            'chunk_count': int(summary.get('chunk_count') or 0),
            'page_count': int(summary.get('page_count') or 0),
            'sheet_count': int(summary.get('sheet_count') or 0),
            'row_count': int(summary.get('row_count') or 0),
            'column_count': int(summary.get('column_count') or 0),
            'image_count': int(summary.get('image_count') or 0),
            'region_types': _json(summary.get('region_types') or []),
            'content_hash': content_hash,
            'size_bytes': max(0, size_bytes),
            'ingestion_job_id': ingestion_job_id,
            'error': error,
            'index_version': index_version,
            'created_at': now,
            'updated_at': now,
        }
        connection = self._connect()
        try:
            connection.execute(
                '''
                INSERT INTO documents (
                    doc_id, source_name, source_path, file_format, modality,
                    language, factory_topic, status, chunk_count, page_count,
                    sheet_count, row_count, column_count, image_count,
                    region_types, content_hash, size_bytes, ingestion_job_id,
                    error, index_version, created_at, updated_at
                ) VALUES (
                    :doc_id, :source_name, :source_path, :file_format, :modality,
                    :language, :factory_topic, :status, :chunk_count, :page_count,
                    :sheet_count, :row_count, :column_count, :image_count,
                    :region_types, :content_hash, :size_bytes, :ingestion_job_id,
                    :error, :index_version, :created_at, :updated_at
                )
                ON CONFLICT(doc_id) DO UPDATE SET
                    source_name = excluded.source_name,
                    source_path = excluded.source_path,
                    file_format = excluded.file_format,
                    modality = excluded.modality,
                    language = excluded.language,
                    factory_topic = excluded.factory_topic,
                    status = excluded.status,
                    chunk_count = excluded.chunk_count,
                    page_count = excluded.page_count,
                    sheet_count = excluded.sheet_count,
                    row_count = excluded.row_count,
                    column_count = excluded.column_count,
                    image_count = excluded.image_count,
                    region_types = excluded.region_types,
                    content_hash = excluded.content_hash,
                    size_bytes = excluded.size_bytes,
                    ingestion_job_id = excluded.ingestion_job_id,
                    error = excluded.error,
                    index_version = excluded.index_version,
                    updated_at = excluded.updated_at
                ''',
                values,
            )
            row = connection.execute(
                'SELECT * FROM documents WHERE doc_id = ?', (values['doc_id'],)
            ).fetchone()
            result = self._document(row)
            assert result is not None
            return result
        finally:
            connection.close()

    def update_review_item(
        self,
        review_id: str,
        *,
        status: str,
        notes: str | None = None,
    ) -> dict[str, object]:
        if status not in {'accepted', 'rejected', 'pending'}:
            raise ValueError('Review status must be pending, accepted, or rejected.')
        self.initialize()
        connection = self._connect()
        try:
            connection.execute(
                '''
                UPDATE review_items SET status = ?, notes = ?, updated_at = ?
                WHERE review_id = ?
                ''',
                (status, notes, _now(), review_id),
            )
            item = self.get_review_item(review_id)
            if item is None:
                raise KeyError(f'Unknown review item: {review_id}')
            return item
        finally:
            connection.close()

    def list_documents(self) -> list[dict[str, object]]:
        self.initialize()
        connection = self._connect()
        try:
            rows = connection.execute(
                'SELECT * FROM documents ORDER BY created_at ASC, doc_id ASC'
            ).fetchall()
            return [
                document
                for row in rows
                if (document := self._document(row, include_internal=False)) is not None
            ]
        finally:
            connection.close()

    def get_document(self, document_id: str) -> dict[str, object] | None:
        self.initialize()
        connection = self._connect()
        try:
            return self._document(
                connection.execute(
                    'SELECT * FROM documents WHERE doc_id = ?', (document_id,)
                ).fetchone()
            )
        finally:
            connection.close()

    def enqueue_job(
        self,
        *,
        document_id: str,
        source_path: str,
        original_filename: str,
        content_hash: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.initialize()
        connection = self._connect()
        try:
            existing = connection.execute(
                'SELECT * FROM ingestion_jobs WHERE idempotency_key = ?',
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                result = self._job(existing)
                assert result is not None
                return result

            active = connection.execute(
                '''
                SELECT * FROM ingestion_jobs
                WHERE doc_id = ? AND status IN ('queued', 'processing')
                ORDER BY queued_at DESC LIMIT 1
                ''',
                (document_id,),
            ).fetchone()
            if active is not None:
                result = self._job(active)
                assert result is not None
                return result

            now = _now()
            job_id = f'job-{uuid4().hex}'
            connection.execute(
                '''
                INSERT INTO ingestion_jobs (
                    job_id, doc_id, source_path, original_filename, content_hash,
                    idempotency_key, status, stage, queued_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', 'queued', ?, ?)
                ''',
                (
                    job_id,
                    document_id,
                    source_path,
                    original_filename,
                    content_hash,
                    idempotency_key,
                    now,
                    now,
                ),
            )
            connection.execute(
                '''
                UPDATE documents
                SET status = 'queued', ingestion_job_id = ?, error = NULL, updated_at = ?
                WHERE doc_id = ?
                ''',
                (job_id, now, document_id),
            )
            self._seed_job_stages(connection, job_id)
            result = self._job(
                connection.execute(
                    'SELECT * FROM ingestion_jobs WHERE job_id = ?', (job_id,)
                ).fetchone()
            )
            assert result is not None
            return result
        finally:
            connection.close()

    def claim_next_job(self) -> dict[str, object] | None:
        self.initialize()
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                '''
                SELECT * FROM ingestion_jobs
                WHERE status = 'queued'
                ORDER BY queued_at ASC
                LIMIT 1
                ''',
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            now = _now()
            connection.execute(
                '''
                UPDATE ingestion_jobs
                SET status = 'processing', stage = 'starting', attempts = attempts + 1,
                    started_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'queued'
                ''',
                (now, now, row['job_id']),
            )
            connection.execute(
                '''
                UPDATE documents
                SET status = 'processing', updated_at = ?
                WHERE doc_id = ?
                ''',
                (now, row['doc_id']),
            )
            connection.commit()
            claimed = connection.execute(
                'SELECT * FROM ingestion_jobs WHERE job_id = ?', (row['job_id'],)
            ).fetchone()
            return self._job(claimed)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def requeue_processing_jobs(self) -> int:
        self.initialize()
        now = _now()
        connection = self._connect()
        try:
            cursor = connection.execute(
                '''
                UPDATE ingestion_jobs
                SET status = 'queued', stage = 'requeued_after_restart',
                    error = 'Worker restarted before the job completed.', updated_at = ?
                WHERE status = 'processing'
                ''',
                (now,),
            )
            connection.execute(
                '''
                UPDATE documents
                SET status = 'queued', error = 'Worker restarted before ingestion completed.',
                    updated_at = ?
                WHERE status = 'processing'
                ''',
                (now,),
            )
            return cursor.rowcount
        finally:
            connection.close()

    def retry_job(self, job_id: str, *, error: str) -> dict[str, object]:
        self.initialize()
        now = _now()
        connection = self._connect()
        try:
            connection.execute(
                '''
                UPDATE ingestion_jobs
                SET status = 'queued', stage = 'retrying', error = ?, updated_at = ?
                WHERE job_id = ?
                ''',
                (error, now, job_id),
            )
            job_row = connection.execute(
                'SELECT * FROM ingestion_jobs WHERE job_id = ?', (job_id,)
            ).fetchone()
            if job_row is None:
                raise KeyError(f'Unknown ingestion job: {job_id}')
            connection.execute(
                '''
                UPDATE documents
                SET status = 'queued', error = ?, updated_at = ?
                WHERE doc_id = ?
                ''',
                (error, now, job_row['doc_id']),
            )
            result = self._job(job_row)
            assert result is not None
            return result
        finally:
            connection.close()

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        stage: str,
        document_status: str | None = None,
        error: str | None = None,
        result: object | None = None,
        document: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        self.initialize()
        now = _now()
        terminal = status in {'indexed', 'failed'}
        connection = self._connect()
        try:
            connection.execute(
                '''
                UPDATE ingestion_jobs
                SET status = ?, stage = ?, error = ?, result = ?,
                    completed_at = CASE WHEN ? THEN ? ELSE completed_at END,
                    updated_at = ?
                WHERE job_id = ?
                ''',
                (status, stage, error, _json(result) if result is not None else None,
                 terminal, now if terminal else None, now, job_id),
            )
            job_row = connection.execute(
                'SELECT * FROM ingestion_jobs WHERE job_id = ?', (job_id,)
            ).fetchone()
            if job_row is None:
                raise KeyError(f'Unknown ingestion job: {job_id}')
            next_document_status = document_status or status
            if document is not None:
                fields = {
                    'source_name': str(document.get('source_name') or ''),
                    'source_path': str(document.get('source_path') or ''),
                    'file_format': str(document.get('format') or 'DOCUMENT').upper(),
                    'modality': str(document.get('modality') or 'document'),
                    'language': str(document.get('language') or 'multilingual'),
                    'factory_topic': str(document.get('factory_topic') or 'factory source'),
                    'chunk_count': int(document.get('chunk_count') or 0),
                    'page_count': int(document.get('page_count') or 0),
                    'sheet_count': int(document.get('sheet_count') or 0),
                    'row_count': int(document.get('row_count') or 0),
                    'column_count': int(document.get('column_count') or 0),
                    'image_count': int(document.get('image_count') or 0),
                    'region_types': _json(document.get('region_types') or []),
                }
                connection.execute(
                    '''
                    UPDATE documents SET
                        source_name = :source_name, source_path = :source_path,
                        file_format = :file_format, modality = :modality,
                        language = :language, factory_topic = :factory_topic,
                        chunk_count = :chunk_count, page_count = :page_count,
                        sheet_count = :sheet_count, row_count = :row_count,
                        column_count = :column_count, image_count = :image_count,
                        region_types = :region_types, status = :status,
                        error = :error, updated_at = :updated_at
                    WHERE doc_id = :doc_id
                    ''',
                    {
                        **fields,
                        'status': next_document_status,
                        'error': error,
                        'updated_at': now,
                        'doc_id': job_row['doc_id'],
                    },
                )
            else:
                connection.execute(
                    '''
                    UPDATE documents SET status = ?, error = ?, updated_at = ?
                    WHERE doc_id = ?
                    ''',
                    (next_document_status, error, now, job_row['doc_id']),
                )
            result = self._job(job_row)
            assert result is not None
            return result
        finally:
            connection.close()

    def get_job(self, job_id: str) -> dict[str, object] | None:
        self.initialize()
        connection = self._connect()
        try:
            return self._job(
                connection.execute(
                    'SELECT * FROM ingestion_jobs WHERE job_id = ?', (job_id,)
                ).fetchone()
            )
        finally:
            connection.close()

    def add_review_item(
        self,
        *,
        job_id: str | None,
        document_id: str,
        chunk_id: str,
        source_ref: str,
        kind: str,
        page: int | None,
        bbox: tuple[float, float, float, float] | None,
        confidence: float | None,
        reason: str,
        status: str = 'pending',
    ) -> dict[str, object]:
        self.initialize()
        now = _now()
        review_id = f'review-{uuid4().hex}'
        connection = self._connect()
        try:
            existing = connection.execute(
                '''
                SELECT review_id FROM review_items
                WHERE doc_id = ? AND chunk_id = ? AND source_ref = ? AND status = 'pending'
                ORDER BY created_at LIMIT 1
                ''',
                (document_id, chunk_id, source_ref),
            ).fetchone()
            if existing is not None:
                return self.get_review_item(existing['review_id']) or {}
            connection.execute(
                '''
                INSERT INTO review_items (
                    review_id, job_id, doc_id, chunk_id, source_ref, kind,
                    page, bbox, confidence, reason, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    review_id,
                    job_id,
                    document_id,
                    chunk_id,
                    source_ref,
                    kind,
                    page,
                    _json(bbox) if bbox else None,
                    confidence,
                    reason,
                    status,
                    now,
                    now,
                ),
            )
            return self.get_review_item(review_id) or {}
        finally:
            connection.close()

    def get_review_item(self, review_id: str) -> dict[str, object] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                'SELECT * FROM review_items WHERE review_id = ?', (review_id,)
            ).fetchone()
            if row is None:
                return None
            return {
                'review_id': row['review_id'],
                'job_id': row['job_id'],
                'doc_id': row['doc_id'],
                'chunk_id': row['chunk_id'],
                'source_ref': row['source_ref'],
                'kind': row['kind'],
                'page': row['page'],
                'bbox': _loads(row['bbox'], None),
                'confidence': row['confidence'],
                'reason': row['reason'],
                'status': row['status'],
                'notes': row['notes'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            }
        finally:
            connection.close()

    def list_review_items(self, status: str | None = None) -> list[dict[str, object]]:
        self.initialize()
        connection = self._connect()
        try:
            if status:
                rows = connection.execute(
                    'SELECT review_id FROM review_items WHERE status = ? ORDER BY created_at',
                    (status,),
                ).fetchall()
            else:
                rows = connection.execute(
                    'SELECT review_id FROM review_items ORDER BY created_at'
                ).fetchall()
            return [
                item
                for row in rows
                if (item := self.get_review_item(row['review_id'])) is not None
            ]
        finally:
            connection.close()

    def set_index_snapshot(
        self,
        *,
        collection_name: str,
        corpus_version: str,
        indexed_documents: int,
        indexed_chunks: int,
    ) -> dict[str, object]:
        self.initialize()
        now = _now()
        connection = self._connect()
        try:
            connection.execute('DELETE FROM index_snapshots')
            connection.execute(
                '''
                INSERT INTO index_snapshots (
                    snapshot_id, collection_name, corpus_version,
                    indexed_documents, indexed_chunks, updated_at
                ) VALUES ('active', ?, ?, ?, ?, ?)
                ''',
                (
                    collection_name,
                    corpus_version,
                    max(0, indexed_documents),
                    max(0, indexed_chunks),
                    now,
                ),
            )
            return self.get_index_snapshot() or {}
        finally:
            connection.close()

    def get_index_snapshot(self) -> dict[str, object] | None:
        self.initialize()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM index_snapshots WHERE snapshot_id = 'active'"
            ).fetchone()
            if row is None:
                return None
            return {
                'collection_name': row['collection_name'],
                'corpus_version': row['corpus_version'],
                'indexed_documents': row['indexed_documents'],
                'indexed_chunks': row['indexed_chunks'],
                'updated_at': row['updated_at'],
            }
        finally:
            connection.close()

    def indexed_counts(self) -> tuple[int, int]:
        self.initialize()
        connection = self._connect()
        try:
            row = connection.execute(
                '''
                SELECT COUNT(*) AS documents, COALESCE(SUM(chunk_count), 0) AS chunks
                FROM documents WHERE status = 'indexed'
                '''
            ).fetchone()
            return int(row['documents']), int(row['chunks'])
        finally:
            connection.close()

    def indexed_corpus_version(self) -> str:
        self.initialize()
        connection = self._connect()
        try:
            rows = connection.execute(
                '''
                SELECT doc_id, content_hash FROM documents
                WHERE status = 'indexed' ORDER BY doc_id
                '''
            ).fetchall()
            material = '|'.join(
                f'{row["doc_id"]}:{row["content_hash"]}' for row in rows
            )
            return hashlib.sha256(material.encode('utf-8')).hexdigest()
        finally:
            connection.close()

    def get_query_cache(self, cache_key: str) -> dict[str, object] | None:
        self.initialize()
        connection = self._connect()
        try:
            now = time.time()
            row = connection.execute(
                'SELECT response_json, expires_at FROM query_cache WHERE cache_key = ?',
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            if float(row['expires_at']) <= now:
                connection.execute('DELETE FROM query_cache WHERE cache_key = ?', (cache_key,))
                return None
            value = _loads(row['response_json'], None)
            return value if isinstance(value, dict) else None
        finally:
            connection.close()

    def put_query_cache(
        self,
        cache_key: str,
        *,
        corpus_version: str,
        prompt_version: str,
        response: Mapping[str, object],
        ttl_seconds: int,
    ) -> None:
        self.initialize()
        connection = self._connect()
        try:
            connection.execute(
                '''
                INSERT INTO query_cache (
                    cache_key, corpus_version, prompt_version, response_json,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    corpus_version = excluded.corpus_version,
                    prompt_version = excluded.prompt_version,
                    response_json = excluded.response_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                ''',
                (
                    cache_key,
                    corpus_version,
                    prompt_version,
                    _json(response),
                    _now(),
                    time.time() + max(1, ttl_seconds),
                ),
            )
        finally:
            connection.close()

    def sync_documents(
        self,
        summaries: Iterable[Mapping[str, object]],
        *,
        project_root: Path = PROJECT_ROOT,
    ) -> list[dict[str, object]]:
        self.initialize()
        synced: list[dict[str, object]] = []
        for summary in summaries:
            raw_path = Path(str(summary.get('source_path') or ''))
            source = raw_path if raw_path.is_absolute() else project_root / raw_path
            existing = self.get_document(str(summary['doc_id']))
            digest = ''
            size = 0
            if source.is_file():
                digest = sha256_file(source)
                size = source.stat().st_size
            preserve_indexed = bool(
                existing
                and existing.get('status') == 'indexed'
                and existing.get('content_hash') == digest
            )
            synced.append(
                self.upsert_document(
                    summary,
                    content_hash=digest,
                    size_bytes=size,
                    status='indexed' if preserve_indexed else 'registered',
                    index_version=existing.get('index_version', '') if preserve_indexed and existing else '',
                )
            )
        return synced
