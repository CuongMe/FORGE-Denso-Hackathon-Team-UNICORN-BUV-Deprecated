from app.generation import GroundedAnswerer
from app.retrieval import HybridRetriever


def test_retriever_returns_cited_torque_evidence():
    results = HybridRetriever().search("What is the target torque for the M6 bolts?", limit=5)

    assert results
    assert results[0].chunk.doc_id == "WI-ASSY-001"
    assert results[0].chunk.chunk_id.startswith("WI-ASSY-001:chunk-")
    assert "9.5" in results[0].chunk.content
    assert any(item.kind == "table" for item in results[0].chunk.provenance)


def test_retriever_matches_english_query_to_vietnamese_evidence():
    results = HybridRetriever().search(
        "What pressure must be zero before zero energy is confirmed?", limit=5
    )

    assert results
    assert results[0].chunk.doc_id == "EHS-ALERT-003"
    assert results[0].chunk.chunk_id.startswith("EHS-ALERT-003:chunk-")


def test_answerer_abstains_when_evidence_is_missing():
    results = HybridRetriever().search("Who won the football match yesterday?", limit=5)
    response = GroundedAnswerer().answer("Who won the football match yesterday?", results)

    assert response.abstained is True
    assert response.citations == []
    assert "don't know" in response.answer.lower()
