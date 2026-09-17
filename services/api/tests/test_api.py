from fastapi.testclient import TestClient

from app import main
from app.persistence import LifecycleStore


client = TestClient(main.app)


def test_health_reports_ready_demo_index():
    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json()['ready'] is True
    assert response.json()['status'] == 'ok'
    assert response.json()['chunks_count'] >= 23
    assert response.json()['ingestion']['chunker'] == 'HybridChunker'
    assert response.json()['graph']['backend'] == 'kuzu'
    assert response.json()['graph']['available'] is True


def test_query_returns_answer_citation_and_retrieval_trace():
    response = client.post(
        '/api/query',
        json={'question': 'What is the target torque for the M6 bolts?'},
    )

    body = response.json()
    assert response.status_code == 200
    assert body['abstained'] is False
    assert body['citations'][0]['chunk_id'].startswith('WI-ASSY-001:chunk-')
    assert body['citations'][0]['provenance']
    assert body['trace']['retrieval_mode'] == 'hybrid'
    assert body['trace']['reranked_count'] > 0
    assert body['trace']['candidates']
    assert body['trace']['candidates'][0]['hybrid_rank'] == 1
    assert any(candidate['rerank_score'] is not None for candidate in body['trace']['candidates'])


def test_query_returns_a_best_match_without_abstaining():
    response = client.post(
        '/api/query',
        json={'question': 'give me knowledge about preventive maintenance'},
    )

    body = response.json()
    assert response.status_code == 200
    assert body['abstained'] is False
    assert body['grounding'] == 'best_match'
    assert body['citations']


def test_graph_returns_live_kuzu_nodes_edges_and_provenance():
    response = client.get(
        '/api/graph',
        params={'node_id': 'source:WI-ASSY-001', 'depth': 1, 'limit': 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body['backend'] == 'kuzu'
    assert body['selected_node'] == 'source:WI-ASSY-001'
    assert any(node['kind'] == 'chunk' for node in body['nodes'])
    assert any(edge['relation'] == 'contains' for edge in body['edges'])
    assert any(edge['provenance_ref'] for edge in body['edges'])


def test_query_rejects_blank_questions_with_structured_error():
    response = client.post('/api/query', json={'question': '   '})

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_upload_rejects_unsupported_file_types():
    response = client.post(
        '/api/documents',
        files={'file': ('malware.exe', b'not a document', 'application/octet-stream')},
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNSUPPORTED_FILE_TYPE'


def test_upload_rejects_content_that_does_not_match_extension():
    response = client.post(
        '/api/documents',
        files={'file': ('inspection.png', b'not a png', 'image/png')},
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_FILE_CONTENT'


def test_upload_accepts_supported_file_and_returns_received_status(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'UPLOAD_ROOT', tmp_path)
    image = b'\x89PNG\r\n\x1a\n' + b'demo-image-bytes'

    response = client.post(
        '/api/documents',
        files={'file': ('inspection.png', image, 'image/png')},
    )

    body = response.json()
    assert response.status_code == 200
    assert body['filename'] == 'inspection.png'
    assert body['status'] == 'received'
    assert (tmp_path / (body['document_id'] + '.png')).read_bytes() == image


def test_production_upload_returns_a_durable_queued_job(tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')

    class FakeRuntime:
        demo_mode = False
        state_store = store

    monkeypatch.setattr(main, 'runtime', FakeRuntime())
    monkeypatch.setattr(main, 'UPLOAD_ROOT', tmp_path / 'uploads')
    pdf = b'%PDF-1.7\nforge upload'

    response = client.post(
        '/api/documents',
        files={'file': ('manual.pdf', pdf, 'application/pdf')},
    )

    body = response.json()
    assert response.status_code == 202
    assert body['status'] == 'queued'
    assert body['job_id'].startswith('job-')
    assert store.get_job(body['job_id'])['status'] == 'queued'


def test_ingestion_job_status_hides_internal_paths(tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.upsert_document(
        {
            'doc_id': 'upload-1',
            'source_name': 'manual.pdf',
            'source_path': 'data/uploads/upload-1.pdf',
            'format': 'PDF',
            'modality': 'pdf',
            'language': 'en',
            'factory_topic': 'uploaded document',
        },
        content_hash='secret-hash',
        size_bytes=10,
        status='queued',
    )
    job = store.enqueue_job(
        document_id='upload-1',
        source_path=str(tmp_path / 'manual.pdf'),
        original_filename='manual.pdf',
        content_hash='secret-hash',
        idempotency_key='upload:secret-hash',
    )
    monkeypatch.setattr(main, 'runtime', type('Runtime', (), {'state_store': store})())

    response = client.get('/api/ingestion/jobs/' + job['job_id'])

    assert response.status_code == 200
    body = response.json()['data']
    assert body['job_id'] == job['job_id']
    assert 'source_path' not in body
    assert 'content_hash' not in body
    assert 'content_hash' not in body['document']


def test_review_endpoints_persist_operator_decisions(tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.upsert_document(
        {
            'doc_id': 'upload-1',
            'source_name': 'inspection.png',
            'source_path': 'data/uploads/upload-1.png',
            'format': 'PNG',
            'modality': 'image',
            'language': 'multilingual',
            'factory_topic': 'uploaded document',
        },
        status='indexed',
    )
    review = store.add_review_item(
        job_id=None,
        document_id='upload-1',
        chunk_id='upload-1:chunk-0000',
        source_ref='#/pictures/1',
        kind='image',
        page=1,
        bbox=(1.0, 2.0, 3.0, 4.0),
        confidence=0.4,
        reason='Low visual confidence.',
    )
    monkeypatch.setattr(main, 'runtime', type('Runtime', (), {'state_store': store})())

    pending = client.get('/api/review-items', params={'status': 'pending'})
    decision = client.patch(
        '/api/review-items/' + str(review['review_id']),
        json={'status': 'accepted', 'notes': 'Confirmed by operator.'},
    )

    assert pending.status_code == 200
    assert pending.json()['total'] == 1
    assert decision.status_code == 200
    assert decision.json()['data']['status'] == 'accepted'
