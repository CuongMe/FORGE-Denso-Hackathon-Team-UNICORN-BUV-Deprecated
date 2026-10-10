from app.document_metadata import summarize_document
from app.models import Chunk


def test_csv_summary_uses_source_shape_and_chunk_count(tmp_path):
    source = tmp_path / 'inspection.csv'
    source.write_text('id,value\n1,ok\n2,hold\n', encoding='utf-8')
    chunk = Chunk(
        chunk_id='csv:chunk-0000',
        doc_id='csv',
        source_name=source.name,
        content='value',
        language='en',
        modality='csv',
    )

    summary = summarize_document(
        source=source,
        doc_id='csv',
        source_name=source.name,
        source_path='uploads/inspection.csv',
        file_format='csv',
        modality='csv',
        language='en',
        factory_topic='inspection',
        chunks=[chunk],
    )

    assert summary['row_count'] == 2
    assert summary['column_count'] == 2
    assert summary['chunk_count'] == 1
    assert summary['page_count'] == 0


def test_xls_summary_includes_sheet_and_table_shape(tmp_path, monkeypatch):
    from app import document_metadata

    source = tmp_path / 'inspection.xls'
    source.write_bytes(b'xls fixture')
    sheet = type('Sheet', (), {'nrows': 3, 'ncols': 2})()
    workbook = type('Workbook', (), {
        'sheet_names': lambda self: ['Inspection'],
        'sheets': lambda self: [sheet],
        'release_resources': lambda self: None,
    })()
    monkeypatch.setattr(document_metadata.xlrd, 'open_workbook', lambda **_: workbook)

    summary = summarize_document(
        source=source, doc_id='xls', source_name=source.name,
        source_path='uploads/inspection.xls', file_format='xls', modality='xls',
        language='en', factory_topic='inspection', chunks=[],
    )

    assert summary['sheet_count'] == 1
    assert summary['row_count'] == 3
    assert summary['column_count'] == 2


def test_pptx_summary_counts_slide_provenance(tmp_path):
    source = tmp_path / 'handover.pptx'
    source.write_bytes(b'pptx fixture')
    chunks = [
        Chunk(chunk_id='pptx:1', doc_id='pptx', source_name=source.name, content='one', language='en', modality='pptx', pages=(1,)),
        Chunk(chunk_id='pptx:2', doc_id='pptx', source_name=source.name, content='two', language='en', modality='pptx', pages=(2,)),
    ]

    summary = summarize_document(
        source=source, doc_id='pptx', source_name=source.name,
        source_path='uploads/handover.pptx', file_format='pptx', modality='pptx',
        language='en', factory_topic='shift handover', chunks=chunks,
    )

    assert summary['page_count'] == 2
