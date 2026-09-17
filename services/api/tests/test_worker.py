from app.persistence import LifecycleStore
from app.worker import IngestionWorker


def _summary() -> dict[str, object]:
    return {
        'doc_id': 'upload-1',
        'source_name': 'inspection.png',
        'source_path': 'data/uploads/upload-1.png',
        'format': 'PNG',
        'modality': 'image',
        'language': 'multilingual',
        'factory_topic': 'uploaded document',
        'chunk_count': 1,
        'page_count': 1,
        'image_count': 1,
        'region_types': ['image'],
    }


def test_worker_claims_and_completes_a_queued_job(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'image')
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(source),
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    class FakeRuntime:
        def ingest(self, source, document_id, source_name, *, job_id):
            assert source == source
            assert document_id == 'upload-1'
            assert source_name == 'inspection.png'
            assert job_id == job['job_id']
            return {'document': _summary(), 'chunk_count': 1, 'review_items': []}

        def refresh_index_snapshot(self):
            pass

    worker = IngestionWorker(FakeRuntime(), store)

    assert worker.run_once() is True
    assert store.get_job(job['job_id'])['status'] == 'indexed'
    assert store.get_document('upload-1')['status'] == 'indexed'


def test_worker_records_a_failed_job_without_losing_the_document(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'image')
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(source),
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    class FailingRuntime:
        def ingest(self, *_args, **_kwargs):
            raise RuntimeError('conversion failed')

        def refresh_index_snapshot(self):
            pass

    worker = IngestionWorker(FailingRuntime(), store, max_attempts=1)

    assert worker.run_once() is True
    assert store.get_job(job['job_id'])['status'] == 'failed'
    assert store.get_document('upload-1')['status'] == 'failed'


def test_worker_retries_transient_failures_before_terminal_failure(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'image')
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(source),
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    class FailingRuntime:
        def ingest(self, *_args, **_kwargs):
            raise RuntimeError('temporary conversion failure')

        def refresh_index_snapshot(self):
            pass

    worker = IngestionWorker(FailingRuntime(), store, max_attempts=2)

    worker.run_once()
    assert store.get_job(job['job_id'])['status'] == 'queued'
    worker.run_once()
    assert store.get_job(job['job_id'])['status'] == 'failed'


def test_worker_persists_live_stage_progress(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'image')
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(source),
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    class FakeRuntime:
        def ingest(self, source, document_id, source_name, *, job_id, progress_callback):
            progress_callback('parsing', 'started', 15, 'Parsing layout.')
            progress_callback('parsing', 'completed', 100, 'Layout parsed.')
            return {'document': _summary(), 'chunk_count': 1, 'review_items': []}

        def refresh_index_snapshot(self):
            pass

    worker = IngestionWorker(FakeRuntime(), store)

    assert worker.run_once() is True
    stages = {stage['stage']: stage for stage in store.get_job_stages(job['job_id'])}
    assert stages['parsing']['status'] == 'completed'
    assert stages['completed']['status'] == 'completed'
