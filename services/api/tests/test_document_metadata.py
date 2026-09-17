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
