from __future__ import annotations

import threading
import logging
import os
import inspect
from pathlib import Path
from typing import Any

from app.persistence import LifecycleStore
from app.pipeline import StageCallback


logger = logging.getLogger(__name__)


class IngestionWorker:
    '''Recoverable at-least-once worker backed by the durable lifecycle store.'''

    def __init__(
        self,
        runtime: Any,
        store: LifecycleStore,
        *,
        poll_interval: float = 0.5,
        max_attempts: int | None = None,
    ) -> None:
        self.runtime = runtime
        self.store = store
        self.poll_interval = max(0.05, poll_interval)
        configured_attempts = max_attempts
        if configured_attempts is None:
            configured_attempts = int(os.getenv('FORGE_INGESTION_MAX_ATTEMPTS', '3'))
        self.max_attempts = max(1, configured_attempts)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> bool:
        job = self.store.claim_next_job()
        if job is None:
            return False
        job_id = str(job['job_id'])
        current_stage = 'uploading'

        def report(stage: str, status: str, progress: int, message: str) -> None:
            nonlocal current_stage
            current_stage = stage
            self.store.update_stage(
                job_id,
                stage,
                status=status,  # type: ignore[arg-type]
                progress=progress,
                message=message,
            )

        try:
            self.store.update_job(job_id, status='processing', stage='uploading')
            report('uploading', 'started', 0, 'Storing the uploaded file for ingestion.')
            report('uploading', 'completed', 100, 'Upload stored; ingestion worker accepted the file.')
            ingest_kwargs: dict[str, object] = {'job_id': job_id}
            ingest_signature = inspect.signature(self.runtime.ingest)
            accepts_callback = 'progress_callback' in ingest_signature.parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in ingest_signature.parameters.values()
            )
            if accepts_callback:
                ingest_kwargs['progress_callback'] = report
            result = self.runtime.ingest(
                Path(str(job['source_path'])),
                str(job['document_id']),
                str(job['original_filename']),
                **ingest_kwargs,
            )
            review_items = result.get('review_items', []) if isinstance(result, dict) else []
            report('completed', 'completed', 100, 'Document indexed and ready for retrieval.')
            self.store.update_job(
                job_id,
                status='indexed',
                stage='completed',
                document_status='indexed',
                result={
                    'chunk_count': int(result.get('chunk_count', 0)) if isinstance(result, dict) else 0,
                    'review_count': len(review_items),
                },
                document=result.get('document') if isinstance(result, dict) else None,
            )
            self.runtime.refresh_index_snapshot()
        except Exception:
            logger.exception('Ingestion job failed: %s', job_id)
            error = 'Ingestion failed. Check service logs for details.'
            if current_stage in {
                'uploading', 'parsing', 'ocr', 'table_extraction', 'vlm_analysis',
                'chunking', 'embedding', 'indexing', 'graph_extraction',
            }:
                try:
                    report(current_stage, 'failed', 100, error)
                except Exception:
                    logger.exception('Could not persist failed stage for job: %s', job_id)
            if int(job['attempts']) < self.max_attempts:
                self.store.retry_job(job_id, error=error)
            else:
                self.store.update_job(
                    job_id,
                    status='failed',
                    stage='failed',
                    document_status='failed',
                    error=error,
                )
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
            name='forge-ingestion-worker',
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval * 4))
            self._thread = None
