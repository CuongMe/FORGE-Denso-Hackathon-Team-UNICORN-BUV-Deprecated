from app import runtime as runtime_module
from app.generation import AnswerDraft
from app.models import Chunk
from app.persistence import LifecycleStore
from app.runtime import RuntimeBundle, build_runtime


def test_runtime_defaults_to_the_deterministic_demo(monkeypatch):
    monkeypatch.delenv('FORGE_RUNTIME_MODE', raising=False)

    runtime = build_runtime()

    assert runtime.mode == 'demo'
    assert runtime.demo_mode is True
    assert runtime.chunks_count > 23
    assert runtime.ingestion()['mode'] == 'demo'


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv('FORGE_RUNTIME_MODE', 'staging')

    try:
        build_runtime()
    except RuntimeError as exc:
        assert 'demo' in str(exc)
        assert 'production' in str(exc)
    else:
        raise AssertionError('build_runtime should reject an unknown runtime mode')


def test_production_runtime_executes_query_without_graph_orchestration():
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
        mode='production',
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


def test_demo_runtime_builds_a_live_kuzu_graph(monkeypatch, tmp_path):
    monkeypatch.delenv('FORGE_RUNTIME_MODE', raising=False)
    monkeypatch.setenv('FORGE_GRAPH_DB_PATH', str(tmp_path / 'forge.kuzu'))

    runtime = build_runtime()

    assert runtime.graph_store is not None
    graph = runtime.graph_store.snapshot(seed_id='source:WI-ASSY-001', depth=1, limit=20)
    assert graph['backend'] == 'kuzu'
    assert graph['selected_node'] == 'source:WI-ASSY-001'
    assert any(node['kind'] == 'chunk' for node in graph['nodes'])


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
