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


def test_answerer_returns_best_match_without_abstaining():
    question = 'give me knowledge about preventive maintenance'
    results = HybridRetriever().search(question, limit=5)
    response = GroundedAnswerer().answer(question, results)

    assert response.abstained is False
    assert response.grounding == 'best_match'
    assert response.citations
    assert response.citations[0].chunk_id == results[0].chunk.chunk_id
    assert response.answer == results[0].chunk.content


def test_answerer_reports_no_match_without_abstaining():
    response = GroundedAnswerer().answer('unrelated question', [])

    assert response.abstained is False
    assert response.grounding == 'no_match'
    assert response.citations == []
    assert 'No matching content' in response.answer
