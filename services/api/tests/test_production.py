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
    ProductionServiceError,
    ProductionHybridRetriever,
    ProductionSettings,
    GeminiGroundedAnswerer,
    DEFAULT_LLM_MODEL,
    DEFAULT_VISUAL_MODEL,
    DEFAULT_VISUAL_PROVIDER,
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


def test_chunks_from_docling_groups_children_under_parent_context():
    records = [
        IngestedChunk(0, "first", (1,), ("Torque",), ()),
        IngestedChunk(1, "second", (1,), ("Torque",), ()),
    ]

    chunks = chunks_from_docling("doc-1", "manual.pdf", "pdf", records)

    assert chunks[0].parent_id == chunks[1].parent_id
    assert chunks[0].parent_title == "Torque"
    assert [chunk.child_index for chunk in chunks] == [0, 1]


def test_production_settings_reads_gemini_key_and_default_model(monkeypatch):
    monkeypatch.delenv("FORGE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FORGE_LLM_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    settings = ProductionSettings.from_env()

    assert settings.llm_api_key == "test-gemini-key"
    assert settings.llm_model == DEFAULT_LLM_MODEL
    assert settings.visual_provider == DEFAULT_VISUAL_PROVIDER
    assert settings.visual_model == DEFAULT_VISUAL_MODEL


def test_production_settings_defaults_to_ten_retrieval_candidates(monkeypatch):
    monkeypatch.delenv('FORGE_RETRIEVAL_LIMIT', raising=False)

    assert ProductionSettings.from_env().retrieval_limit == 10


def test_production_settings_reads_embedding_batch_size(monkeypatch):
    monkeypatch.setenv('FORGE_EMBED_BATCH_SIZE', '96')

    assert ProductionSettings.from_env().embed_batch_size == 96


def test_dense_encoder_receives_configured_embedding_batch_size():
    class FakeDenseEncoder:
        def __init__(self):
            self.kwargs = None

        def encode_document(self, texts, **kwargs):
            self.kwargs = kwargs
            return [[0.1, 0.2] for _ in texts]

    dense = FakeDenseEncoder()
    settings = replace(_settings(), embed_batch_size=7)
    retriever = ProductionHybridRetriever(
        settings,
        qdrant_client=object(),
        dense_encoder=dense,
        sparse_encoder=object(),
        qdrant_models=object(),
    )

    assert retriever._encode_documents(['one', 'two']) == [[0.1, 0.2], [0.1, 0.2]]
    assert dense.kwargs['batch_size'] == 7


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
            assert "Vietnamese questions about Japanese evidence in Vietnamese" in kwargs["config"].system_instruction
            return SimpleNamespace(text="Use 9.5 ± 0.5 N·m.")

    class FakeClient:
        models = FakeModels()

    answerer = GeminiGroundedAnswerer(_settings(), client=FakeClient())
    result = answerer.answer("What is the torque?", [_candidate().model_copy(update={"rerank_score": 0.91})])

    assert result.abstained is False
    assert result.answer.startswith("Use 9.5")
    assert result.citations[0].chunk_id == "doc-1:chunk-0000"


def test_gemini_answerer_preserves_abstention_and_provider_usage():
    class FakeModels:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(
                text=ABSTENTION_TEXT,
                usage_metadata=SimpleNamespace(
                    prompt_token_count=120,
                    candidates_token_count=14,
                    total_token_count=134,
                ),
            )

    class FakeClient:
        models = FakeModels()

    settings = replace(
        _settings(),
        input_usd_per_million=0.10,
        output_usd_per_million=0.40,
    )
    result = GeminiGroundedAnswerer(settings, client=FakeClient()).answer(
        'What is absent from the source pack?',
        [_candidate().model_copy(update={'rerank_score': 0.91})],
    )

    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.grounding == 'no_match'
    assert result.citations == []
    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 14
    assert result.usage.total_tokens == 134
    assert result.usage.estimated_cost_usd == pytest.approx(0.0000176)


def test_gemini_answerer_abstains_when_no_evidence_is_retrieved():
    result = GeminiGroundedAnswerer(_settings(), client=object()).answer(
        'What is absent from the source pack?',
        [],
    )

    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.grounding == 'no_match'
    assert result.citations == []


def test_gemini_answerer_abstains_before_calling_provider_below_evidence_threshold():
    class FakeModels:
        def generate_content(self, **_kwargs):
            raise AssertionError('weak evidence must not reach the provider')

    class FakeClient:
        models = FakeModels()

    answerer = GeminiGroundedAnswerer(_settings(), client=FakeClient())
    result = answerer.answer('What is the torque?', [_candidate().model_copy(update={'rerank_score': 0.2})])

    assert result.abstained is True
    assert result.grounding == 'no_match'
    assert result.citations == []
    assert result.answer == ABSTENTION_TEXT


def test_gemini_answerer_allows_lower_score_for_image_explanation_queries():
    class FakeModels:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(text='The image shows a factory inspection view.')

    class FakeClient:
        models = FakeModels()

    image_candidate = _candidate().model_copy(
        update={
            'rerank_score': 0.2,
            'chunk': _candidate().chunk.model_copy(
                update={
                    'source_name': 'inspection.jpg',
                    'source_path': 'data/inspection.jpg',
                    'modality': 'image',
                    'content': 'Factory inspection image region.',
                }
            ),
        }
    )

    result = GeminiGroundedAnswerer(_settings(), client=FakeClient()).answer(
        'Giải thích ảnh này.',
        [image_candidate],
    )

    assert result.abstained is False
    assert result.answer.startswith('The image shows')


def test_gemini_answerer_only_cites_evidence_relevant_to_generated_answer():
    class FakeModels:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(text='Use 9.5 ± 0.5 N·m.')

    class FakeClient:
        models = FakeModels()

    unrelated = RetrievedChunk(
        chunk=Chunk(
            chunk_id='doc-2:chunk-0000',
            doc_id='doc-2',
            source_name='maintenance.pdf',
            content='The inspection interval is every 30 days.',
            language='en',
            modality='pdf',
            page=4,
            region='Maintenance schedule',
        ),
        hybrid_score=0.8,
        rerank_score=0.89,
    )

    answerer = GeminiGroundedAnswerer(_settings(), client=FakeClient())
    result = answerer.answer(
        'What is the torque?',
        [_candidate().model_copy(update={'rerank_score': 0.91}), unrelated],
    )

    assert [citation.chunk_id for citation in result.citations] == ['doc-1:chunk-0000']


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


def test_production_retriever_filters_search_to_document_scope():
    class FakeDenseEncoder:
        def encode_query(self, text, **_kwargs):
            return [[0.1, 0.2]]

    class FakeSparse:
        indices = [4]
        values = [0.7]

    class FakeSparseEncoder:
        def embed(self, texts, **_kwargs):
            return (FakeSparse() for _ in texts)

    class Filter:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FieldCondition:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class MatchValue:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeModels:
        class SparseVector:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class Prefetch:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class Fusion:
            RRF = 'rrf'

        class FusionQuery:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

    FakeModels.Filter = Filter
    FakeModels.FieldCondition = FieldCondition
    FakeModels.MatchValue = MatchValue

    class FakeClient:
        def query_points(self, **kwargs):
            self.query = kwargs
            return SimpleNamespace(points=[])

    client = FakeClient()
    retriever = ProductionHybridRetriever(
        _settings(),
        qdrant_client=client,
        dense_encoder=FakeDenseEncoder(),
        sparse_encoder=FakeSparseEncoder(),
        qdrant_models=FakeModels,
    )
    retriever._collection_ready = True

    retriever.search('Explain this source.', document_id='upload-123')

    source_filter = client.query['query_filter']
    condition = source_filter.must[0]
    assert condition.key == 'doc_id'
    assert condition.match.value == 'upload-123'


def test_existing_qdrant_collection_must_match_named_vector_schema():
    class FakeDenseEncoder:
        def encode_document(self, texts, **_kwargs):
            return [[0.1, 0.2] for _ in texts]

    class FakeClient:
        def collection_exists(self, **_kwargs):
            return True

        def get_collection(self, **_kwargs):
            return SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(
                        vectors={'dense': SimpleNamespace(size=3)},
                        sparse_vectors={'sparse': SimpleNamespace()},
                    )
                )
            )

    retriever = ProductionHybridRetriever(
        _settings(),
        qdrant_client=FakeClient(),
        dense_encoder=FakeDenseEncoder(),
        sparse_encoder=object(),
        qdrant_models=SimpleNamespace(),
    )

    with pytest.raises(ProductionServiceError, match='dense vector dimension'):
        retriever.ensure_collection()
