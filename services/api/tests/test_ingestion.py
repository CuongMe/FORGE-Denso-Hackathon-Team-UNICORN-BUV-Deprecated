from types import SimpleNamespace

from app.ingestion import extract_chunk_provenance, ingestion_status


def test_ingestion_status_exposes_supported_formats_and_chunker():
    status = ingestion_status()

    assert status["chunker"] == "HybridChunker"
    assert ".pdf" in status["supported_extensions"]
    assert ".png" in status["supported_extensions"]
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
