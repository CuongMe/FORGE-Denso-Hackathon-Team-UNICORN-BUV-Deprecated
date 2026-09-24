from pathlib import Path

from app import corpus
from app.corpus import load_source_pack_chunks
from app.ingestion import IngestedChunk


class RecordingAdapter:
    tokenizer_name = 'local-whitespace'
    cache_key = 'local-whitespace:384'

    def __init__(self) -> None:
        self.sources: list[Path] = []

    def _max_tokens(self) -> int:
        return 384

    def convert_and_chunk(self, source: Path) -> list[IngestedChunk]:
        self.sources.append(source)
        return [
            IngestedChunk(
                chunk_index=0,
                text=f'Extracted content from {source.name}',
                page_numbers=(1,),
                headings=('Source content',),
                captions=(),
            )
        ]


def test_source_registry_converts_every_manifest_file_without_qa_anchors(tmp_path):
    adapter = RecordingAdapter()

    chunks = load_source_pack_chunks(adapter, cache_path=tmp_path / 'chunks.json')

    assert len(adapter.sources) == 17
    assert {source.suffix.casefold() for source in adapter.sources} == {
        '.pdf',
        '.png',
        '.jpg',
        '.xlsx',
        '.csv',
    }
    assert len(chunks) == 17
    assert all('Question anchor:' not in chunk.content for chunk in chunks)
    assert all(chunk.source_path.startswith('data/denso_factory_hack_data_prep/') for chunk in chunks)


def test_curated_pdfs_can_be_enabled_explicitly(tmp_path, monkeypatch):
    monkeypatch.setenv('FORGE_INCLUDE_CURATED_DOCUMENTS', 'true')
    curated = tmp_path / 'curated_documents'
    curated.mkdir()
    for name in ('reference-a.pdf', 'reference-b.pdf', 'reference-c.pdf'):
        (curated / name).write_bytes(b'%PDF-1.4 test fixture')
    monkeypatch.setattr(corpus, 'CURATED_ROOT', curated)
    adapter = RecordingAdapter()

    chunks = load_source_pack_chunks(adapter, cache_path=tmp_path / 'curated.json')

    assert len(adapter.sources) == 20
    assert sum(source.parent.name == 'curated_documents' for source in adapter.sources) == 3
    assert len(chunks) == 20


def test_source_registry_reuses_only_a_matching_content_cache(tmp_path):
    cache_path = tmp_path / 'chunks.json'
    first_adapter = RecordingAdapter()
    load_source_pack_chunks(first_adapter, cache_path=cache_path)

    second_adapter = RecordingAdapter()
    chunks = load_source_pack_chunks(second_adapter, cache_path=cache_path)

    assert second_adapter.sources == []
    assert len(chunks) == 17
