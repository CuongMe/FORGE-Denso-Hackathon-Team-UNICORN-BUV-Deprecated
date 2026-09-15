from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.models import Chunk, RetrievedChunk
from app.ingestion import IngestedChunk, IngestedProvenance
from app.production import (
    ABSTENTION_TEXT,
    ProductionCrossEncoderReranker,
    ProductionDependencyError,
    ProductionHybridRetriever,
    ProductionSettings,
    GeminiGroundedAnswerer,
    DEFAULT_LLM_MODEL,
    chunks_from_docling,
)


def _settings() -> ProductionSettings:
    return ProductionSettings(
        qdrant_url="http://qdrant.test:6333",
        qdrant_api_key=None,
        collection_name="forge_test",
        dense_model="BAAI/bge-m3",
        sparse_model="Qdrant/bm25",
        reranker_model="BAAI/bge-reranker-v2-m3",
        llm_model="gemini-2.5-flash-lite",
        llm_api_key="test-key",
        retrieval_limit=20,
        rerank_limit=2,
        evidence_threshold=0.45,
    )


def _candidate() -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id="doc-1:chunk-0000",
            doc_id="doc-1",
            source_name="manual.pdf",
            content="The target torque is 9.5 ± 0.5 N·m.",
            language="en",
            modality="pdf",
            page=2,
            region="Torque table",
        ),
        lexical_score=0.4,
        semantic_score=0.7,
        hybrid_score=0.6,
    )


def test_production_settings_reads_gemini_key_and_default_model(monkeypatch):
    monkeypatch.delenv("FORGE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FORGE_LLM_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    settings = ProductionSettings.from_env()

    assert settings.llm_api_key == "test-gemini-key"
    assert settings.llm_model == DEFAULT_LLM_MODEL


def test_production_cross_encoder_reranks_pairs_and_normalizes_scores():
    class FakeCrossEncoder:
        def __init__(self):
            self.pairs = None

        def predict(self, pairs, **_kwargs):
            self.pairs = pairs
            return [-2.0]

    model = FakeCrossEncoder()
    reranker = ProductionCrossEncoderReranker(_settings(), model=model)

    results = reranker.rerank("What is the torque?", [_candidate()])

    assert model.pairs == [["What is the torque?", "The target torque is 9.5 ± 0.5 N·m."]]
    assert results[0].rerank_score is not None
    assert 0.11 < results[0].rerank_score < 0.12


def test_gemini_answerer_uses_grounded_output_and_server_owned_citations():
    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-2.5-flash-lite"
            assert "9.5" in kwargs["contents"]
            assert "Answer only from the supplied evidence." in kwargs["config"].system_instruction
            return SimpleNamespace(text="Use 9.5 ± 0.5 N·m.")

    class FakeClient:
        models = FakeModels()

    answerer = GeminiGroundedAnswerer(_settings(), client=FakeClient())
    result = answerer.answer("What is the torque?", [_candidate().model_copy(update={"rerank_score": 0.91})])

    assert result.abstained is False
    assert result.answer.startswith("Use 9.5")
    assert result.citations[0].chunk_id == "doc-1:chunk-0000"


def test_gemini_answerer_fails_closed_below_evidence_threshold():
    answerer = GeminiGroundedAnswerer(_settings(), client=object())

    result = answerer.answer("What is the torque?", [_candidate().model_copy(update={"rerank_score": 0.2})])

    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.citations == []


def test_gemini_answerer_requires_an_api_key_for_live_generation():
    answerer = GeminiGroundedAnswerer(replace(_settings(), llm_api_key=None))

    with pytest.raises(ProductionDependencyError, match="GEMINI_API_KEY"):
        answerer.answer(
            "What is the torque?",
            [_candidate().model_copy(update={"rerank_score": 0.91})],
        )


def test_chunks_from_docling_preserves_provenance_and_source_identity():
    records = [
        IngestedChunk(
            chunk_index=3,
            text="## Torque\nUse 9.5 N·m.",
            page_numbers=(4,),
            headings=("Torque",),
            captions=(),
            provenance=(
                IngestedProvenance(
                    ref="#/tables/1",
                    kind="table",
                    page=4,
                    bbox=(1.0, 2.0, 3.0, 4.0),
                    coord_origin="BOTTOMLEFT",
                ),
            ),
        )
    ]

    chunks = chunks_from_docling(
        "upload-123",
        "manual.pdf",
        "pdf",
        records,
        source_path="data/uploads/manual.pdf",
    )

    assert chunks[0].chunk_id == "upload-123:chunk-0003"
    assert chunks[0].doc_id == "upload-123"
    assert chunks[0].page == 4
    assert chunks[0].region == "Torque"
    assert chunks[0].source_path == "data/uploads/manual.pdf"
    assert chunks[0].provenance[0].ref == "#/tables/1"
    assert chunks[0].provenance[0].bbox == (1.0, 2.0, 3.0, 4.0)


def test_qdrant_retriever_upserts_named_vectors_and_fuses_results():
    class FakeSparse:
        indices = [4, 9]
        values = [0.7, 0.3]

    class FakeDenseEncoder:
        def encode_document(self, texts, **_kwargs):
            return [[0.1, 0.2] for _ in texts]

        def encode_query(self, _text, **_kwargs):
            return [0.1, 0.2]

    class FakeSparseEncoder:
        def embed(self, texts, **_kwargs):
            return (FakeSparse() for _ in texts)

    class FakeModels:
        class Distance:
            COSINE = "Cosine"

        class Modifier:
            IDF = "idf"

        class SparseVector:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class VectorParams:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class SparseVectorParams:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class PointStruct:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class Prefetch:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class Fusion:
            RRF = "rrf"

        class FusionQuery:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

    class FakeClient:
        def __init__(self):
            self.points = []
            self.collection_created = False

        def collection_exists(self, **_kwargs):
            return self.collection_created

        def create_collection(self, **_kwargs):
            self.collection_created = True

        def upsert(self, *, points, **_kwargs):
            self.points = points

        def query_points(self, **_kwargs):
            return SimpleNamespace(
                points=[SimpleNamespace(score=0.8, payload=self.points[0].payload)]
            )

    client = FakeClient()
    retriever = ProductionHybridRetriever(
        _settings(),
        qdrant_client=client,
        dense_encoder=FakeDenseEncoder(),
        sparse_encoder=FakeSparseEncoder(),
        qdrant_models=FakeModels,
    )

    assert retriever.upsert_chunks([_candidate().chunk]) == 1
    results = retriever.search("What is the torque?", limit=1)

    UUID(client.points[0].id)
    assert client.points[0].payload["chunk_id"] == "doc-1:chunk-0000"
    assert client.points[0].vector["sparse"].indices == [4, 9]
    assert results[0].chunk.chunk_id == "doc-1:chunk-0000"
    assert results[0].hybrid_score == 0.8
