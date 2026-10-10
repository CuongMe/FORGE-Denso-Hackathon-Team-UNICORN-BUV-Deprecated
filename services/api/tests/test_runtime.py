from app import runtime as runtime_module
from app.generation import AnswerDraft
from app.models import Chunk, RetrievedChunk
from app.persistence import LifecycleStore
from app.runtime import RuntimeBundle, build_runtime
from app.visual import Florence2VisualDescriber


def test_runtime_defaults_to_production(monkeypatch, tmp_path):
    monkeypatch.delenv('FORGE_RUNTIME_MODE', raising=False)
    monkeypatch.setenv('FORGE_STATE_DB_PATH', str(tmp_path / 'forge.sqlite3'))

    runtime = build_runtime()

    assert runtime.chunks_count == 0
    assert runtime.ingestion()['mode'] == 'production'


def test_runtime_defaults_to_florence2_for_visual_enrichment(monkeypatch):
    class InMemoryStore:
        database = ':memory:'

        def initialize(self):
            return None

        def requeue_processing_jobs(self):
            return None

        def sync_documents(self, _documents):
            return None

    monkeypatch.setattr(runtime_module, 'LifecycleStore', InMemoryStore)
    monkeypatch.delenv('FORGE_VISUAL_PROVIDER', raising=False)

    runtime = build_runtime()

    assert isinstance(
        runtime.ingestion_service.chunker.visual_describer,
        Florence2VisualDescriber,
    )


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv('FORGE_RUNTIME_MODE', 'staging')

    try:
        build_runtime()
    except RuntimeError as exc:
        assert 'production' in str(exc)
    else:
        raise AssertionError('build_runtime should reject an unknown runtime mode')


def test_production_runtime_executes_query():
    calls: list[str] = []

    class Retriever:
        settings = type('Settings', (), {'retrieval_limit': 4})()

        def search(self, question, *, limit):
            calls.append(f'retrieve:{question}:{limit}')
            return ['candidate']

    class Reranker:
        settings = type('Settings', (), {'rerank_limit': 2})()

        def rerank(self, question, candidates, *, limit):
            calls.append(f'rerank:{question}:{len(candidates)}:{limit}')
            return ['ranked']

    class Answerer:
        def answer(self, question, results):
            calls.append(f'answer:{question}:{len(results)}')
            return AnswerDraft('Direct answer', False, [])

    runtime = RuntimeBundle(
        chunks=(),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=Answerer(),
    )

    execution = runtime.execute_query('What is the torque?')

    assert calls == [
        'retrieve:What is the torque?:4',
        'rerank:What is the torque?:1:2',
        'answer:What is the torque?:1',
    ]
    assert execution.candidates == ['candidate']
    assert execution.ranked == ['ranked']
    assert execution.draft.answer == 'Direct answer'


def test_production_runtime_passes_document_scope_to_retrieval():
    calls: list[tuple[str, int, str | None]] = []

    class Retriever:
        settings = type('Settings', (), {'retrieval_limit': 4})()

        def search(self, question, *, limit, document_id=None):
            calls.append((question, limit, document_id))
            return ['candidate']

    class Reranker:
        settings = type('Settings', (), {'rerank_limit': 2})()

        def rerank(self, question, candidates, *, limit):
            return ['ranked']

    class Answerer:
        def answer(self, question, results):
            return AnswerDraft('Direct answer', False, [])

    runtime = RuntimeBundle(
        chunks=(),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=Answerer(),
    )

    runtime.execute_query('Explain this source.', document_id='upload-123')

    assert calls == [('Explain this source.', 4, 'upload-123')]


def test_production_runtime_marks_referenced_document_as_exact_match():
    candidate = RetrievedChunk(
        chunk=Chunk(
            chunk_id='upload-123:chunk-0000',
            doc_id='upload-123',
            source_name='diagram.jpg',
            content='Japanese OCR evidence',
            language='ja',
            modality='image',
        ),
        hybrid_score=0.5,
        rerank_score=0.000034,
    )

    class Retriever:
        settings = type('Settings', (), {'retrieval_limit': 4})()

        def search(self, _question, *, limit, document_id=None):
            assert limit == 4
            assert document_id == 'upload-123'
            return [candidate]

    class Reranker:
        settings = type('Settings', (), {'rerank_limit': 2})()

        def rerank(self, _question, candidates, *, limit):
            assert limit == 2
            return candidates

    class Answerer:
        def answer(self, _question, results):
            assert results[0].rerank_score == 1.0
            return AnswerDraft('Direct answer', False, [])

    runtime = RuntimeBundle(
        chunks=(),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=Answerer(),
    )

    execution = runtime.execute_query('Explain this source.', document_id='upload-123')

    assert execution.ranked[0].rerank_score == 1.0


def test_runtime_warms_query_models_without_requiring_visual_model():
    calls: list[str] = []

    class Retriever:
        def warm(self):
            calls.append('retriever')

    class Reranker:
        def warm(self):
            calls.append('reranker')

    class Answerer:
        def warm(self):
            calls.append('answerer')

    runtime = RuntimeBundle(
        chunks=(),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=Answerer(),
    )

    runtime.warm_models()

    assert calls == ['retriever', 'reranker', 'answerer']


def test_image_query_excludes_unrelated_pdf_and_adds_indexed_image_sources():
    pdf = Chunk(
        chunk_id='pdf:chunk-0000',
        doc_id='SUP-PACK-20260915',
        source_name='packing-list.pdf',
        source_path='data/packing-list.pdf',
        content='Supplier packing list',
        language='en',
        modality='pdf',
    )
    hmi = Chunk(
        chunk_id='IMG-HMI-001:chunk-0000',
        doc_id='IMG-HMI-001',
        source_name='machine_alarm_hmi.png',
        source_path='data/machine_alarm_hmi.png',
        content='E-214 VISION CAMERA NO TRIGGER. Time: 2026-09-15 10:57:13.',
        language='en',
        modality='HMI screenshot',
    )
    checksheet = Chunk(
        chunk_id='IMG-CHECK-001:chunk-0000',
        doc_id='IMG-CHECK-001',
        source_name='scan_checksheet_rotated.png',
        source_path='data/scan_checksheet_rotated.png',
        content='Daily start-up check sheet.',
        language='en',
        modality='rotated noisy scan',
    )
    hmi_recovery = hmi.model_copy(
        update={
            'chunk_id': 'IMG-HMI-001:chunk-0001',
            'content': 'Recovery instructions for the alarm.',
        }
    )

    class Retriever:
        def search(self, _question, *, limit):
            assert limit == 8
            return [
                RetrievedChunk(chunk=pdf, hybrid_score=0.9),
                RetrievedChunk(chunk=hmi_recovery, hybrid_score=0.2),
            ]

    class Reranker:
        def rerank(self, _question, candidates, *, limit):
            assert limit == 5
            return candidates

    class Answerer:
        def answer(self, _question, results):
            self.results = results
            return AnswerDraft('Image answer', False, [])

    answerer = Answerer()
    runtime = RuntimeBundle(
        chunks=(hmi, checksheet),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=answerer,
    )

    execution = runtime.execute_query('List images and identify the latest error image.')

    assert {item.chunk.doc_id for item in execution.candidates} == {
        'IMG-HMI-001',
        'IMG-CHECK-001',
    }
    assert 'IMG-HMI-001:chunk-0000' in {
        item.chunk.chunk_id for item in execution.candidates
    }
    assert all(item.chunk.doc_id != 'SUP-PACK-20260915' for item in answerer.results)


def test_vietnamese_image_query_uses_image_sources():
    image = Chunk(
        chunk_id='IMG-001:chunk-0000',
        doc_id='IMG-001',
        source_name='inspection.jpg',
        content='Metal inspection image.',
        language='multilingual',
        modality='image',
    )
    pdf = Chunk(
        chunk_id='PDF-001:chunk-0000',
        doc_id='PDF-001',
        source_name='manual.pdf',
        content='Maintenance manual.',
        language='vi',
        modality='pdf',
    )

    class Retriever:
        def search(self, _question, *, limit):
            return [
                RetrievedChunk(chunk=pdf, hybrid_score=0.9),
                RetrievedChunk(chunk=image, hybrid_score=0.2),
            ]

    class Reranker:
        def rerank(self, _question, candidates, *, limit):
            return candidates

    class Answerer:
        def answer(self, _question, results):
            assert [item.chunk.doc_id for item in results] == ['IMG-001']
            return AnswerDraft('Image answer', False, [])

    runtime = RuntimeBundle(
        chunks=(image,),
        retriever=Retriever(),
        reranker=Reranker(),
        answerer=Answerer(),
    )

    runtime.execute_query('Tìm một số ảnh trong nguồn.')


def test_production_runtime_registers_source_pack_documents(monkeypatch, tmp_path):
    source_chunk = Chunk(
        chunk_id='WI-ASSY-001:chunk-0000',
        doc_id='WI-ASSY-001',
        source_name='work-instruction.pdf',
        content='Torque evidence',
        language='en',
        modality='pdf',
    )
    monkeypatch.setenv('FORGE_RUNTIME_MODE', 'production')
    monkeypatch.setenv('FORGE_INCLUDE_SOURCE_PACK', '1')
    monkeypatch.setenv('FORGE_STATE_DB_PATH', str(tmp_path / 'forge.sqlite3'))
    monkeypatch.setattr(runtime_module, 'load_source_pack_chunks', lambda: [source_chunk])
    monkeypatch.setattr(
        runtime_module,
        'list_demo_documents',
        lambda chunks: [{'doc_id': chunks[0].doc_id, 'chunk_count': len(chunks)}],
    )

    runtime = build_runtime()

    assert runtime.chunks_count == 0
    assert runtime.document_list()[0]['doc_id'] == 'WI-ASSY-001'
    assert runtime.document_list()[0]['status'] == 'registered'


def test_production_runtime_persists_unindexed_source_documents(monkeypatch, tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF-demo')
    source_chunk = Chunk(
        chunk_id='WI-ASSY-001:chunk-0000',
        doc_id='WI-ASSY-001',
        source_name='work-instruction.pdf',
        content='Torque evidence',
        language='en',
        modality='pdf',
        source_path='source.pdf',
        page=1,
    )
    monkeypatch.setenv('FORGE_RUNTIME_MODE', 'production')
    monkeypatch.setenv('FORGE_INCLUDE_SOURCE_PACK', '1')
    monkeypatch.setenv('FORGE_STATE_DB_PATH', str(tmp_path / 'forge.sqlite3'))
    monkeypatch.setattr(runtime_module, 'load_source_pack_chunks', lambda: [source_chunk])
    monkeypatch.setattr(
        runtime_module,
        'list_demo_documents',
        lambda chunks: [{
            'doc_id': chunks[0].doc_id,
            'source_name': 'work-instruction.pdf',
            'source_path': str(source),
            'format': 'PDF',
            'modality': 'pdf',
            'language': 'en',
            'factory_topic': 'work instruction',
            'status': 'ready',
            'chunk_count': len(chunks),
            'page_count': 1,
            'sheet_count': 0,
            'row_count': 0,
            'column_count': 0,
            'image_count': 0,
            'region_types': ['text'],
        }],
    )

    runtime = build_runtime()

    store = LifecycleStore(tmp_path / 'forge.sqlite3')
    assert runtime.document_list()[0]['status'] == 'registered'
    assert store.get_document('WI-ASSY-001')['status'] == 'registered'
    assert runtime.chunks_count == 0
