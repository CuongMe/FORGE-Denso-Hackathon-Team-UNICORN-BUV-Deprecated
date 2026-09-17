import pytest

from app.models import Chunk, ChunkProvenance


def _chunk(
    *,
    chunk_id: str,
    doc_id: str,
    source_name: str,
    content: str,
    page: int,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        source_name=source_name,
        content=content,
        language='en',
        modality='pdf',
        source_path=f'data/curated_documents/{source_name}',
        page=page,
        region='Torque table',
        region_type='table',
        provenance=(
            ChunkProvenance(
                ref='#/tables/1',
                kind='table',
                page=page,
                bbox=(1.0, 2.0, 3.0, 4.0),
                coord_origin='BOTTOMLEFT',
            ),
        ),
    )


def test_kuzu_graph_store_preserves_provenance_and_related_documents(tmp_path):
    pytest.importorskip('kuzu')
    from app.graph_store import KuzuGraphStore

    chunks = [
        _chunk(
            chunk_id='doc-1:chunk-0003',
            doc_id='doc-1',
            source_name='assembly.pdf',
            content='M6 bolt torque is 9.5 N.m. Verify calibration before assembly.',
            page=4,
        ),
        _chunk(
            chunk_id='doc-2:chunk-0001',
            doc_id='doc-2',
            source_name='inspection.pdf',
            content='Torque inspection validates the M6 bolt assembly result.',
            page=2,
        ),
    ]
    documents = [
        {
            'doc_id': 'doc-1',
            'source_name': 'assembly.pdf',
            'source_path': 'data/curated_documents/assembly.pdf',
            'format': 'PDF',
            'modality': 'pdf',
            'status': 'indexed',
            'factory_topic': 'assembly',
        },
        {
            'doc_id': 'doc-2',
            'source_name': 'inspection.pdf',
            'source_path': 'data/curated_documents/inspection.pdf',
            'format': 'PDF',
            'modality': 'pdf',
            'status': 'indexed',
            'factory_topic': 'inspection',
        },
    ]

    store = KuzuGraphStore(tmp_path / 'forge.kuzu')
    store.sync_documents(documents, chunks)

    graph = store.snapshot(seed_id='source:doc-1', depth=2, limit=50)
    nodes = {node['id']: node for node in graph['nodes']}
    edges = graph['edges']

    assert graph['selected_node'] == 'source:doc-1'
    assert nodes['source:doc-1']['kind'] == 'source'
    assert nodes['chunk:doc-1:chunk-0003']['page'] == 4
    assert nodes['chunk:doc-1:chunk-0003']['region'] == 'Torque table'
    assert any(
        edge['source'] == 'source:doc-1'
        and edge['target'] == 'chunk:doc-1:chunk-0003'
        and edge['relation'] == 'contains'
        for edge in edges
    )
    assert any(
        edge['target'] == 'concept:torque'
        and edge['provenance_ref'] == '#/tables/1'
        and edge['page'] == 4
        for edge in edges
    )
    assert any(
        edge['source'] == 'source:doc-1'
        and edge['target'] == 'source:doc-2'
        and edge['relation'] == 'related'
        for edge in edges
    )

