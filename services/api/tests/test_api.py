from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health_reports_ready_demo_index():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["chunks_count"] >= 23
    assert response.json()["ingestion"]["chunker"] == "HybridChunker"


def test_query_returns_answer_citation_and_retrieval_trace():
    response = client.post(
        "/api/query",
        json={"question": "What is the target torque for the M6 bolts?"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["abstained"] is False
    assert body["citations"][0]["chunk_id"].startswith("WI-ASSY-001:chunk-")
    assert body["citations"][0]["provenance"]
    assert body["trace"]["retrieval_mode"] == "hybrid"
    assert body["trace"]["reranked_count"] > 0


def test_query_rejects_blank_questions_with_structured_error():
    response = client.post("/api/query", json={"question": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_unsupported_file_types():
    response = client.post(
        "/api/documents",
        files={"file": ("malware.exe", b"not a document", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_upload_accepts_supported_file_and_returns_received_status(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOAD_ROOT", tmp_path)

    response = client.post(
        "/api/documents",
        files={"file": ("inspection.png", b"demo-image-bytes", "image/png")},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["filename"] == "inspection.png"
    assert body["status"] == "received"
    assert (tmp_path / f"{body['document_id']}.png").read_bytes() == b"demo-image-bytes"
