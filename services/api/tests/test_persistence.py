from app.persistence import LifecycleStore


def _summary(doc_id: str = 'upload-1') -> dict[str, object]:
    return {
        'doc_id': doc_id,
        'source_name': 'inspection.png',
        'source_path': 'data/uploads/upload-1.png',
        'format': 'PNG',
        'modality': 'image',
        'language': 'multilingual',
        'factory_topic': 'uploaded document',
        'status': 'registered',
        'chunk_count': 1,
        'page_count': 1,
        'sheet_count': 0,
        'row_count': 0,
        'column_count': 0,
        'image_count': 1,
        'region_types': ['picture'],
    }


def test_lifecycle_store_persists_documents_jobs_and_index_snapshot(tmp_path):
    database = tmp_path / 'forge.sqlite3'
    source = tmp_path / 'upload-1.png'
    source.write_bytes(b'image')

    store = LifecycleStore(database)
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(source),
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed['job_id'] == job['job_id']
    assert claimed['status'] == 'processing'

    store.update_job(
        job['job_id'],
        status='indexed',
        stage='complete',
        document_status='indexed',
        result={'chunk_count': 1},
    )
    store.set_index_snapshot(
        collection_name='forge_chunks',
        corpus_version='sha-1',
        indexed_documents=1,
        indexed_chunks=1,
    )

    reopened = LifecycleStore(database)
    assert reopened.get_document('upload-1')['status'] == 'indexed'
    assert reopened.get_job(job['job_id'])['result'] == {'chunk_count': 1}
    assert reopened.get_index_snapshot()['indexed_chunks'] == 1


def test_claim_next_job_is_idempotent_for_active_document(tmp_path):
    database = tmp_path / 'forge.sqlite3'
    store = LifecycleStore(database)
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')

    first = store.enqueue_job(
        document_id='upload-1',
        source_path='upload-1.png',
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )
    duplicate = store.enqueue_job(
        document_id='upload-1',
        source_path='upload-1.png',
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    assert duplicate['job_id'] == first['job_id']
    assert store.claim_next_job()['job_id'] == first['job_id']
    assert store.claim_next_job() is None


def test_processing_jobs_are_requeued_after_restart(tmp_path):
    database = tmp_path / 'forge.sqlite3'
    store = LifecycleStore(database)
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path='upload-1.png',
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )
    assert store.claim_next_job()['status'] == 'processing'

    reopened = LifecycleStore(database)
    reopened.requeue_processing_jobs()

    assert reopened.get_job(job['job_id'])['status'] == 'queued'


def test_job_stage_timeline_is_seeded_and_persists_updates(tmp_path):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='queued')
    job = store.enqueue_job(
        document_id='upload-1',
        source_path='upload-1.png',
        original_filename='inspection.png',
        content_hash='sha-1',
        idempotency_key='upload:sha-1',
    )

    stages = store.get_job_stages(job['job_id'])

    assert [stage['stage'] for stage in stages] == [
        'queued', 'uploading', 'parsing', 'ocr', 'table_extraction',
        'vlm_analysis', 'chunking', 'embedding', 'indexing',
        'graph_extraction', 'completed',
    ]
    assert stages[0]['status'] == 'completed'
    assert stages[1]['status'] == 'pending'

    store.update_stage(
        job['job_id'],
        'vlm_analysis',
        status='started',
        progress=40,
        message='Analyzing visual regions.',
    )
    reopened = LifecycleStore(store.database)
    current = next(item for item in reopened.get_job_stages(job['job_id']) if item['stage'] == 'vlm_analysis')

    assert current['status'] == 'started'
    assert current['progress'] == 40
    assert current['message'] == 'Analyzing visual regions.'


def test_review_items_preserve_provenance_and_can_be_decided(tmp_path):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    store.upsert_document(_summary(), content_hash='sha-1', size_bytes=5, status='processing')

    review = store.add_review_item(
        job_id=None,
        document_id='upload-1',
        chunk_id='upload-1:chunk-0000',
        source_ref='#/pictures/1',
        kind='image',
        page=2,
        bbox=(1.0, 2.0, 3.0, 4.0),
        confidence=0.61,
        reason='Visual description requires human review.',
    )
    updated = store.update_review_item(
        str(review['review_id']),
        status='accepted',
        notes='Confirmed by operator.',
    )

    assert updated['status'] == 'accepted'
    assert updated['bbox'] == [1.0, 2.0, 3.0, 4.0]
    assert updated['notes'] == 'Confirmed by operator.'
