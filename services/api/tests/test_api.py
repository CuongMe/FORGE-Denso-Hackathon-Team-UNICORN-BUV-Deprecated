from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app import main
from app.evaluation import EvaluationStore
from app.generation import AnswerDraft
from app.models import Chunk, ChunkProvenance, Citation, RetrievedChunk
from app.persistence import LifecycleStore
from app.runtime import QueryExecution


class FakeRuntime:
    def __init__(self, store):
        self.state_store = store
        self.retriever = SimpleNamespace(settings=SimpleNamespace(
            retrieval_limit=8,
            rerank_limit=5,
            dense_model='fake-dense',
            sparse_model='fake-sparse',
            reranker_model='fake-reranker',
            llm_model='fake-gemini',
        ))
        self.reranker = SimpleNamespace(name='fake-reranker')
        self.answerer = SimpleNamespace(evidence_threshold=0.45)

    @property
    def chunks_count(self):
        return self.state_store.indexed_counts()[1]

    def document_list(self):
        return self.state_store.list_documents()

    def readiness(self):
        return {'ready': True, 'checks': {'providers': 'ready'}}

    def ingestion(self):
        return {'mode': 'production', 'chunker': 'HybridChunker'}

    def refresh_index_snapshot(self):
        return None

    def execute_query(self, question):
        best_match = 'preventive maintenance' in question.casefold()
        chunk = Chunk(
            chunk_id='WI-ASSY-001:chunk-0000',
            doc_id='WI-ASSY-001',
            source_name='manual.pdf',
            source_path='data/manual.pdf',
            content='The target torque for M6 bolts is 9.5 N m.',
            language='en',
            modality='pdf',
            page=1,
            pages=(1,),
            region='Torque specification',
            provenance=(ChunkProvenance(ref='#/text/1', kind='text', page=1),),
        )
        candidate = RetrievedChunk(
            chunk=chunk,
            lexical_score=0.8,
            semantic_score=0.9,
            hybrid_score=0.85,
            rerank_score=0.2 if best_match else 0.95,
        )
        citation = Citation(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            source_name=chunk.source_name,
            source_path=chunk.source_path,
            page=chunk.page,
            pages=chunk.pages,
            region=chunk.region,
            provenance=chunk.provenance,
            quote=chunk.content,
            score=candidate.rerank_score,
        )
        return QueryExecution(
            candidates=[candidate],
            ranked=[candidate],
            draft=AnswerDraft(
                'Preventive maintenance guidance.' if best_match else 'Use 9.5 N m.',
                False,
                [citation],
                'best_match' if best_match else 'grounded',
            ),
        )


@pytest.fixture
def client(tmp_path, monkeypatch):
    lifecycle = LifecycleStore(tmp_path / 'forge.sqlite3')
    metrics = EvaluationStore(str(tmp_path / 'metrics.sqlite3'))
    metrics.initialize()
    monkeypatch.setattr(main, 'runtime', FakeRuntime(lifecycle))
    monkeypatch.setattr(main, 'evaluation_store', metrics)
    monkeypatch.setattr(main, 'readiness_cache', main.ReadinessCache())
    with TestClient(main.app) as test_client:
        yield test_client


def test_query_metrics_capture_success_and_failure_without_provider_calls(client, tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.evaluation import EvaluationStore
    from app.models import QueryResponse, RetrievalTrace

    store = EvaluationStore(str(tmp_path / 'metrics.sqlite3'))
    store.initialize()
    monkeypatch.setattr(main, 'evaluation_store', store)
    answer = QueryResponse(answer='Local test', abstained=False, citations=[],
        trace=RetrievalTrace(candidates_considered=0, reranked_count=0,
                            reranker='test', evidence_threshold=.45, latency_ms=1))
    monkeypatch.setattr(main, '_execute_query', lambda _: answer)
    assert client.post('/api/query', json={'question': 'local test'}).status_code == 200

    def fail(_):
        raise HTTPException(503, 'Test provider unavailable')

    monkeypatch.setattr(main, '_execute_query', fail)
    assert client.post('/api/query', json={'question': 'local test'}).status_code == 503
    assert client.post('/api/query', json={'question': ' '}).status_code == 422
    metrics = client.get('/api/metrics').json()
    assert metrics['total_queries'] == 2
    assert metrics['success_rate'] == .5


def test_quality_endpoints_require_configured_admin_key(client, monkeypatch):
    monkeypatch.setenv('FORGE_ADMIN_API_KEY', 'competition-secret')

    missing = client.get('/api/metrics')
    wrong = client.get('/api/evaluations', headers={'X-Forge-Admin-Key': 'wrong'})
    allowed = client.get(
        '/api/metrics',
        headers={'X-Forge-Admin-Key': 'competition-secret'},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert allowed.status_code == 200


def test_health_reports_production_index_status(client):
    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['chunks_count'] >= 0
    assert 'demo_mode' not in response.json()
    assert response.json()['ingestion']['mode'] == 'production'
    assert response.json()['ingestion']['chunker'] == 'HybridChunker'


def test_query_returns_answer_citation_and_retrieval_trace(client):
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


def test_query_returns_a_best_match_without_abstaining(client):
    response = client.post(
        '/api/query',
        json={'question': 'give me knowledge about preventive maintenance'},
    )

    body = response.json()
    assert response.status_code == 200
    assert body['abstained'] is False
    assert body['grounding'] == 'best_match'
    assert body['citations']


def test_query_rejects_blank_questions_with_structured_error(client):
    response = client.post('/api/query', json={'question': '   '})

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_document_reference_is_removed_from_semantic_question():
    from app.main import _split_document_reference

    question, document_id = _split_document_reference(
        '@upload-123 explain this source to me'
    )

    assert question == 'explain this source to me'
    assert document_id == 'upload-123'


def test_upload_rejects_unsupported_file_types(client):
    response = client.post(
        '/api/documents',
        files={'file': ('malware.exe', b'not a document', 'application/octet-stream')},
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'UNSUPPORTED_FILE_TYPE'


def test_upload_rejects_content_that_does_not_match_extension(client):
    response = client.post(
        '/api/documents',
        files={'file': ('inspection.png', b'not a png', 'image/png')},
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_FILE_CONTENT'


def test_xls_signature_is_accepted():
    assert main._content_matches_extension('.xls', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1workbook')
    assert not main._content_matches_extension('.xls', b'not an xls workbook')


def test_upload_accepts_bmp_signature(client, tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    store.initialize()
    monkeypatch.setattr(main, 'runtime', type('Runtime', (), {'state_store': store})())
    monkeypatch.setattr(main, 'UPLOAD_ROOT', tmp_path / 'uploads')
    bmp = b'BM' + b'\x00' * 30

    response = client.post(
        '/api/documents',
        files={'file': ('inspection.bmp', bmp, 'image/bmp')},
    )

    assert response.status_code != 422


def test_production_upload_returns_a_durable_queued_job(client, tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')

    class FakeRuntime:
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


def test_ingestion_job_status_hides_internal_paths(client, tmp_path, monkeypatch):
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


def test_review_endpoints_persist_operator_decisions(client, tmp_path, monkeypatch):
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


def test_csv_preview_renders_in_browser(client, tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    source = tmp_path / 'inspection.csv'
    source.write_text('part,score\nM6 bolt,9.5\n', encoding='utf-8')
    store.upsert_document(
        {
            'doc_id': 'preview-csv',
            'source_name': 'inspection.csv',
            'source_path': 'inspection.csv',
            'format': 'CSV',
            'modality': 'table',
            'language': 'en',
            'factory_topic': 'inspection',
        },
        status='indexed',
    )
    monkeypatch.setattr(main, 'runtime', type('Runtime', (), {'state_store': store})())
    monkeypatch.setattr(main, 'PROJECT_ROOT', tmp_path)

    response = client.get('/api/documents/preview-csv/preview')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'M6 bolt' in response.text
    assert 'inspection.csv' in response.text


def test_xls_preview_renders_sheets_as_tables(client, tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    source = tmp_path / 'inspection.xls'
    source.write_bytes(b'xls fixture')
    store.upsert_document({
        'doc_id': 'preview-xls', 'source_name': source.name,
        'source_path': source.name, 'format': 'XLS', 'modality': 'table',
        'language': 'en', 'factory_topic': 'inspection',
    }, status='indexed')
    monkeypatch.setattr(main, 'runtime', type('Runtime', (), {'state_store': store})())
    monkeypatch.setattr(main, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(main, 'read_table_sheets', lambda *_args, **_kwargs: [
        ('Inspection', [['part', 'status'], ['M6 bolt', 'ok']]),
    ])

    response = client.get('/api/documents/preview-xls/preview')

    assert response.status_code == 200
    assert 'Inspection' in response.text
    assert 'M6 bolt' in response.text
