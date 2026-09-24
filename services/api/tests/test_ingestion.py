from types import SimpleNamespace

from app.ingestion import DoclingHybridChunkerAdapter, IngestedChunk, IngestedProvenance
from app.visual import VisualDescription

from app.ingestion import extract_chunk_provenance, ingestion_status


def test_ingestion_status_exposes_supported_formats_and_chunker():
    status = ingestion_status()

    assert status["chunker"] == "HybridChunker"
    assert ".pdf" in status["supported_extensions"]
    assert ".png" in status["supported_extensions"]
    assert ".bmp" in status["supported_extensions"]
    assert status["backend"] in {"unavailable", "docling-hybridchunker"}


def test_extract_chunk_provenance_keeps_table_ref_page_and_coordinates():
    class TableItem:
        self_ref = "#/tables/4"
        label = SimpleNamespace(value="table")
        prov = [
            SimpleNamespace(
                page_no=3,
                bbox=SimpleNamespace(
                    l=10.0,
                    t=20.0,
                    r=110.0,
                    b=80.0,
                    coord_origin=SimpleNamespace(value="TOPLEFT"),
                ),
            )
        ]

    chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[TableItem()]))

    provenance = extract_chunk_provenance(chunk)

    assert provenance[0].ref == "#/tables/4"
    assert provenance[0].kind == "table"
    assert provenance[0].page == 3
    assert provenance[0].bbox == (10.0, 20.0, 110.0, 80.0)
    assert provenance[0].coord_origin == "TOPLEFT"


def test_extract_chunk_provenance_keeps_table_identity_without_fake_page():
    class CsvTableItem:
        self_ref = "#/tables/0"
        label = SimpleNamespace(value="table")
        prov = []

    chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[CsvTableItem()]))

    provenance = extract_chunk_provenance(chunk)

    assert provenance[0].ref == "#/tables/0"
    assert provenance[0].kind == "table"
    assert provenance[0].page is None


def test_visual_enrichment_adds_description_and_keeps_low_confidence_for_review(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'image')

    class FakeVisualDescriber:
        def describe(self, source_path, *, region_ref, page):
            assert source_path == source
            assert region_ref == '#/pictures/1'
            assert page == 2
            return VisualDescription(
                description='A pressure gauge reads 0.0 MPa.',
                confidence=0.61,
                review_required=False,
            )

    adapter = DoclingHybridChunkerAdapter(visual_describer=FakeVisualDescriber())
    records = [
        IngestedChunk(
            chunk_index=0,
            text='Image region #/pictures/1',
            page_numbers=(2,),
            headings=(),
            captions=(),
            provenance=(
                IngestedProvenance(
                    ref='#/pictures/1',
                    kind='image',
                    page=2,
                    bbox=(1.0, 2.0, 3.0, 4.0),
                    coord_origin='TOPLEFT',
                ),
            ),
        )
    ]

    enriched = adapter._enrich_visual_records(source, records)

    assert 'A pressure gauge reads 0.0 MPa.' in enriched[0].text
    assert enriched[0].review_candidates[0].confidence == 0.61
    assert enriched[0].review_candidates[0].reason
