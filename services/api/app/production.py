from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv

from app.document_metadata import summarize_document
from app.generation import ABSTENTION_TEXT, NO_MATCH_TEXT, AnswerDraft
from app.ingestion import DoclingHybridChunkerAdapter, IngestedChunk
from app.models import Chunk, ChunkProvenance, Citation, RetrievedChunk, TokenUsage
from app.pipeline import StageCallback
from app.persistence import LifecycleStore


DEFAULT_DENSE_MODEL = "BAAI/bge-m3"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"
DEFAULT_VISUAL_PROVIDER = "florence2"
DEFAULT_VISUAL_MODEL = "microsoft/Florence-2-base-ft"
IMAGE_QUERY_TERMS = frozenset({
    'image', 'images', 'img', 'photo', 'photos', 'picture', 'pictures',
    'screenshot', 'screenshots', 'visual', 'visuals', 'ảnh', 'hình', 'hinh',
})

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _offline_model_mode() -> bool:
    return os.getenv("FORGE_HF_OFFLINE", "1").strip().casefold() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _query_requests_image_sources(question: str) -> bool:
    tokens = set(re.findall(r'\w+', question.casefold(), flags=re.UNICODE))
    return bool(tokens & IMAGE_QUERY_TERMS)


if _offline_model_mode():
    # Keep normal application startup independent of Hugging Face availability.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


class ProductionDependencyError(RuntimeError):
    """Raised when an explicitly selected production dependency is unavailable."""


class ProductionServiceError(RuntimeError):
    """Raised when a configured production service cannot complete an operation."""


def _resolve_model_source(model_name: str, component: str) -> str:
    """Resolve a model to a local Hugging Face snapshot in offline mode."""
    model_path = Path(model_name).expanduser()
    if model_path.is_dir():
        return str(model_path)
    if not _offline_model_mode():
        return model_name

    try:
        from huggingface_hub import snapshot_download

        return snapshot_download(repo_id=model_name, local_files_only=True)
    except Exception as exc:
        raise ProductionServiceError(
            f"The {component} model is not available in the local Hugging Face cache: "
            f"{model_name}. Set FORGE_HF_OFFLINE=0 once to download it, then restart offline."
        ) from exc


@dataclass(frozen=True, slots=True)
class ProductionSettings:
    qdrant_url: str
    qdrant_api_key: str | None
    collection_name: str
    dense_model: str
    sparse_model: str
    reranker_model: str
    llm_model: str
    llm_api_key: str | None
    retrieval_limit: int
    rerank_limit: int
    evidence_threshold: float
    input_usd_per_million: float = 0.0
    output_usd_per_million: float = 0.0
    embed_batch_size: int = 64
    visual_provider: str = DEFAULT_VISUAL_PROVIDER
    visual_model: str = DEFAULT_VISUAL_MODEL

    @classmethod
    def from_env(cls) -> "ProductionSettings":
        qdrant_url = os.getenv("FORGE_QDRANT_URL", "http://127.0.0.1:6333")
        qdrant_api_key = os.getenv("FORGE_QDRANT_API_KEY") or None
        if qdrant_url.startswith(("http://127.0.0.1", "http://localhost")):
            qdrant_api_key = None
        return cls(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            collection_name=os.getenv("FORGE_QDRANT_COLLECTION", "forge_chunks"),
            dense_model=os.getenv("FORGE_DENSE_MODEL", DEFAULT_DENSE_MODEL),
            sparse_model=os.getenv("FORGE_SPARSE_MODEL", DEFAULT_SPARSE_MODEL),
            reranker_model=os.getenv("FORGE_RERANKER_MODEL", DEFAULT_RERANKER_MODEL),
            llm_model=os.getenv("FORGE_LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_api_key=(
                os.getenv("FORGE_GEMINI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("FORGE_LLM_API_KEY")
                or None
            ),
            retrieval_limit=max(1, int(os.getenv("FORGE_RETRIEVAL_LIMIT", "10"))),
            rerank_limit=max(1, int(os.getenv("FORGE_RERANK_LIMIT", "5"))),
            evidence_threshold=float(os.getenv("FORGE_EVIDENCE_THRESHOLD", "0.45")),
            input_usd_per_million=max(0.0, float(os.getenv('FORGE_GEMINI_INPUT_USD_PER_MILLION', '0'))),
            output_usd_per_million=max(0.0, float(os.getenv('FORGE_GEMINI_OUTPUT_USD_PER_MILLION', '0'))),
            embed_batch_size=max(1, min(512, int(os.getenv('FORGE_EMBED_BATCH_SIZE', '64')))),
            visual_provider=os.getenv('FORGE_VISUAL_PROVIDER', DEFAULT_VISUAL_PROVIDER).strip().casefold(),
            visual_model=os.getenv('FORGE_VISUAL_MODEL', DEFAULT_VISUAL_MODEL).strip(),
        )


def _vector_batch(raw: Any) -> list[list[float]]:
    """Convert numpy/torch/list output to a plain list for Qdrant."""
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    if not raw:
        return []
    if isinstance(raw[0], (int, float)):
        raw = [raw]
    return [[float(value) for value in vector] for vector in raw]


class ProductionHybridRetriever:
    """Qdrant dense+sparse retrieval with server-side reciprocal rank fusion."""

    name = "qdrant-dense-sparse-rrf"

    def __init__(
        self,
        settings: ProductionSettings | None = None,
        *,
        qdrant_client: Any | None = None,
        dense_encoder: Any | None = None,
        sparse_encoder: Any | None = None,
        qdrant_models: Any | None = None,
    ) -> None:
        self.settings = settings or ProductionSettings.from_env()
        self._client = qdrant_client
        self._dense_encoder = dense_encoder
        self._sparse_encoder = sparse_encoder
        self._models = qdrant_models
        self._collection_ready = False

    def _load_dependencies(self) -> None:
        if self._models is None or self._client is None:
            try:
                from qdrant_client import QdrantClient, models
            except ImportError as exc:
                raise ProductionDependencyError(
                    "Production retrieval requires qdrant-client. "
                    "Install services/api/requirements-production.txt."
                ) from exc
            self._models = models
            if self._client is None:
                self._client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key,
                )

        if self._dense_encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ProductionDependencyError(
                    "Production retrieval requires sentence-transformers. "
                    "Install services/api/requirements-production.txt."
                ) from exc
            try:
                dense_source = _resolve_model_source(self.settings.dense_model, "dense embedding")
                self._dense_encoder = SentenceTransformer(
                    dense_source,
                    local_files_only=_offline_model_mode(),
                )
            except Exception as exc:
                raise ProductionServiceError(
                    f"The dense model could not be loaded: {self.settings.dense_model}."
                ) from exc

        if self._sparse_encoder is None:
            try:
                from fastembed import SparseTextEmbedding
            except ImportError as exc:
                raise ProductionDependencyError(
                    "Production retrieval requires fastembed for sparse search. "
                    "Install services/api/requirements-production.txt."
                ) from exc
            try:
                self._sparse_encoder = SparseTextEmbedding(model_name=self.settings.sparse_model)
            except Exception as exc:
                raise ProductionServiceError(
                    f"The sparse model could not be loaded: {self.settings.sparse_model}."
                ) from exc

    def warm(self) -> None:
        """Load local retrieval models before the first user request."""
        self._load_dependencies()

    @property
    def client(self) -> Any:
        self._load_dependencies()
        return self._client

    def _encode_documents(self, texts: list[str]) -> list[list[float]]:
        self._load_dependencies()
        encoder = self._dense_encoder
        method = getattr(encoder, "encode_document", None) or getattr(encoder, "encode")
        try:
            encoded = method(
                texts,
                batch_size=self.settings.embed_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise ProductionServiceError("The dense encoder failed to embed document text.") from exc
        vectors = _vector_batch(encoded)
        if len(vectors) != len(texts):
            raise ProductionServiceError("The dense encoder returned an unexpected vector count.")
        return vectors

    def _encode_query(self, text: str) -> list[float]:
        self._load_dependencies()
        encoder = self._dense_encoder
        method = getattr(encoder, "encode_query", None) or getattr(encoder, "encode")
        try:
            encoded = method(text, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise ProductionServiceError("The dense encoder failed to embed the query.") from exc
        vectors = _vector_batch(encoded)
        if not vectors:
            raise ProductionServiceError("The dense encoder returned an empty query vector.")
        return vectors[0]

    def _encode_sparse(self, texts: list[str]) -> list[Any]:
        self._load_dependencies()
        try:
            embeddings = list(self._sparse_encoder.embed(texts, batch_size=self.settings.embed_batch_size))
        except Exception as exc:
            raise ProductionServiceError("The sparse encoder failed to embed text.") from exc
        if len(embeddings) != len(texts):
            raise ProductionServiceError("The sparse encoder returned an unexpected vector count.")
        return embeddings

    def _sparse_vector(self, embedding: Any) -> Any:
        self._load_dependencies()
        return self._models.SparseVector(
            indices=[int(value) for value in embedding.indices],
            values=[float(value) for value in embedding.values],
        )

    def ensure_collection(self) -> None:
        if self._collection_ready:
            return
        self._load_dependencies()
        try:
            if self.client.collection_exists(collection_name=self.settings.collection_name):
                self._validate_collection_schema()
                self._collection_ready = True
                return

            probe = self._encode_documents(["FORGE vector dimension probe"])[0]
            self.client.create_collection(
                collection_name=self.settings.collection_name,
                vectors_config={
                    "dense": self._models.VectorParams(
                        size=len(probe), distance=self._models.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": self._models.SparseVectorParams(modifier=self._models.Modifier.IDF)
                },
            )
        except (ProductionDependencyError, ProductionServiceError):
            raise
        except Exception as exc:
            raise ProductionServiceError(
                f"Qdrant collection '{self.settings.collection_name}' is unavailable."
            ) from exc
        self._collection_ready = True

    def _validate_collection_schema(self) -> None:
        '''Reject an existing collection created for a different embedding contract.'''
        try:
            collection = self.client.get_collection(collection_name=self.settings.collection_name)
            params = collection.config.params
            vectors = getattr(params, 'vectors', None)
            sparse_vectors = getattr(params, 'sparse_vectors', None)
            dense = vectors.get('dense') if isinstance(vectors, dict) else None
            sparse = sparse_vectors.get('sparse') if isinstance(sparse_vectors, dict) else None
            dimension = getattr(dense, 'size', None)
            if dense is None or dimension is None:
                raise ProductionServiceError(
                    'Qdrant collection must expose a named dense vector called dense.'
                )
            if sparse is None:
                raise ProductionServiceError(
                    'Qdrant collection must expose a named sparse vector called sparse.'
                )
            expected_dimension = len(self._encode_documents(['FORGE vector dimension probe'])[0])
            if int(dimension) != expected_dimension:
                raise ProductionServiceError(
                    f'Qdrant dense vector dimension {dimension} does not match '
                    f'the embedding model dimension {expected_dimension}.'
                )
        except ProductionServiceError:
            raise
        except Exception as exc:
            raise ProductionServiceError(
                f'Qdrant collection {self.settings.collection_name} has an invalid schema.'
            ) from exc

    def count_points(self) -> int:
        '''Return the exact point count used by readiness checks.'''
        self.ensure_collection()
        try:
            result = self.client.count(
                collection_name=self.settings.collection_name,
                exact=True,
            )
            return max(0, int(getattr(result, 'count', result)))
        except Exception as exc:
            raise ProductionServiceError('Qdrant point count is unavailable.') from exc

    def upsert_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        progress_callback: StageCallback | None = None,
    ) -> int:
        records = list(chunks)
        if not records:
            if progress_callback:
                progress_callback('embedding', 'completed', 100, 'No chunks required embedding.')
                progress_callback('indexing', 'completed', 100, 'No chunks required indexing.')
            return 0
        if progress_callback:
            progress_callback('embedding', 'started', 0, f'Generating BGE-M3 embeddings for {len(records)} chunk(s).')
        try:
            self.ensure_collection()
            texts = [record.content for record in records]
            dense_vectors = self._encode_documents(texts)
            sparse_vectors = self._encode_sparse(texts)
        except (ProductionDependencyError, ProductionServiceError):
            if progress_callback:
                progress_callback('embedding', 'failed', 100, 'Embedding generation failed.')
            raise
        if progress_callback:
            progress_callback('embedding', 'completed', 100, f'Generated embeddings for {len(records)} chunk(s).')
        points = [
            self._models.PointStruct(
                # Qdrant accepts integer or UUID point IDs; keep the readable
                # chunk_id in the payload used for citations.
                id=str(uuid5(NAMESPACE_URL, f"forge:{record.doc_id}:{record.chunk_id}")),
                vector={
                    "dense": dense,
                    "sparse": self._sparse_vector(sparse),
                },
                payload=record.model_dump(mode="json"),
            )
            for record, dense, sparse in zip(records, dense_vectors, sparse_vectors, strict=True)
        ]
        if progress_callback:
            progress_callback('indexing', 'started', 0, f'Upserting {len(points)} chunk(s) into Qdrant.')
        try:
            self.client.upsert(
                collection_name=self.settings.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            if progress_callback:
                progress_callback('indexing', 'failed', 100, 'Qdrant rejected the chunk upsert.')
            raise ProductionServiceError("Qdrant rejected the chunk upsert.") from exc
        if progress_callback:
            progress_callback('indexing', 'completed', 100, f'Indexed {len(points)} chunk(s) in Qdrant.')
        return len(points)

    def search(
        self,
        question: str,
        limit: int = 8,
        *,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        if limit < 1:
            return []
        self.ensure_collection()
        dense_query = self._encode_query(question)
        sparse_query = self._sparse_vector(self._encode_sparse([question])[0])
        prefetch_limit = max(limit * 4, 20)
        query_filter = None
        if document_id:
            query_filter = self._models.Filter(
                must=[
                    self._models.FieldCondition(
                        key='doc_id',
                        match=self._models.MatchValue(value=document_id),
                    )
                ]
            )
        try:
            response = self.client.query_points(
                collection_name=self.settings.collection_name,
                prefetch=[
                    self._models.Prefetch(
                        query=dense_query,
                        using="dense",
                        limit=prefetch_limit,
                    ),
                    self._models.Prefetch(
                        query=sparse_query,
                        using="sparse",
                        limit=prefetch_limit,
                    ),
                ],
                query=self._models.FusionQuery(fusion=self._models.Fusion.RRF),
                query_filter=query_filter,
                with_payload=True,
                limit=limit,
            )
        except Exception as exc:
            raise ProductionServiceError("Qdrant hybrid search failed.") from exc
        results: list[RetrievedChunk] = []
        for point in response.points:
            payload = point.payload or {}
            try:
                chunk = Chunk.model_validate(payload)
            except Exception:
                continue
            score = float(getattr(point, "score", 0.0) or 0.0)
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    hybrid_score=score,
                )
            )
        return results


class ProductionCrossEncoderReranker:
    """Multilingual late-stage reranking for the small candidate set."""

    def __init__(
        self,
        settings: ProductionSettings | None = None,
        *,
        model: Any | None = None,
    ) -> None:
        self.settings = settings or ProductionSettings.from_env()
        self._model = model
        self.name = f"sentence-transformers:{self.settings.reranker_model}"

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise ProductionDependencyError(
                    "Production reranking requires sentence-transformers. "
                    "Install services/api/requirements-production.txt."
                ) from exc
            try:
                reranker_source = _resolve_model_source(self.settings.reranker_model, "reranker")
                self._model = CrossEncoder(
                    reranker_source,
                    max_length=512,
                    local_files_only=_offline_model_mode(),
                )
            except Exception as exc:
                raise ProductionServiceError(
                    f"The reranker model could not be loaded: {self.settings.reranker_model}."
                ) from exc
        return self._model

    def warm(self) -> None:
        """Load the cross-encoder before the first user request."""
        _ = self.model

    @staticmethod
    def _score(value: Any) -> float:
        score = float(value)
        if not math.isfinite(score):
            return 0.0
        if 0.0 <= score <= 1.0:
            return round(score, 6)
        score = max(-60.0, min(60.0, score))
        return round(1.0 / (1.0 + math.exp(-score)), 6)

    def rerank(
        self,
        question: str,
        candidates: list[RetrievedChunk],
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        if not candidates or limit < 1:
            return []
        pairs = [
            [question, candidate.chunk.content]
            for candidate in candidates
        ]
        try:
            scores = self.model.predict(pairs, batch_size=len(pairs), show_progress_bar=False)
        except Exception as exc:
            raise ProductionServiceError("The cross-encoder reranker failed to score candidates.") from exc
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        reranked = [
            candidate.model_copy(update={"rerank_score": self._score(score)})
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        return sorted(reranked, key=lambda item: item.rerank_score or 0.0, reverse=True)[:limit]


class GeminiGroundedAnswerer:
    """Generate only from retrieved evidence and fail closed on missing evidence."""

    def __init__(
        self,
        settings: ProductionSettings | None = None,
        *,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or ProductionSettings.from_env()
        self.evidence_threshold = self.settings.evidence_threshold
        self._client = client

    @property
    def name(self) -> str:
        return f"gemini:{self.settings.llm_model}"

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.settings.llm_api_key:
                raise ProductionDependencyError(
                    "Production generation requires GEMINI_API_KEY or FORGE_LLM_API_KEY."
                )
            try:
                from google import genai
            except ImportError as exc:
                raise ProductionDependencyError(
                    "Production generation requires the google-genai package. "
                    "Install services/api/requirements-production.txt."
                ) from exc
            self._client = genai.Client(api_key=self.settings.llm_api_key)
        return self._client

    def warm(self) -> None:
        """Initialize the Gemini client without spending a generation request."""
        _ = self.client

    def answer(self, question: str, results: list[RetrievedChunk]) -> AnswerDraft:
        if not results:
            return AnswerDraft(
                answer=ABSTENTION_TEXT,
                abstained=True,
                citations=[],
                grounding='no_match',
            )
        best_score = results[0].rerank_score
        evidence_threshold = (
            min(self.evidence_threshold, 0.20)
            if _query_requests_image_sources(question)
            else self.evidence_threshold
        )
        if best_score is None or best_score < evidence_threshold:
            return AnswerDraft(
                answer=ABSTENTION_TEXT,
                abstained=True,
                citations=[],
                grounding='no_match',
            )

        evidence = "\n\n".join(
            f"[{candidate.chunk.chunk_id}] {candidate.chunk.source_name}, "
            f"pages {candidate.chunk.pages or 'not recorded'}, "
            f"region {candidate.chunk.region}\n"
            f"{candidate.chunk.content}"
            for candidate in results[: self.settings.rerank_limit]
        )
        try:
            from google.genai import types
        except ImportError as exc:
            raise ProductionDependencyError(
                "Production generation requires the google-genai package. "
                "Install services/api/requirements-production.txt."
            ) from exc

        try:
            response = self.client.models.generate_content(
                model=self.settings.llm_model,
                contents=f"Question:\n{question}\n\nEvidence:\n{evidence}",
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are FORGE, a factory operations assistant. "
                        "Answer only from the supplied evidence. "
                        "If the evidence is weak or incomplete, clearly state that uncertainty. "
                        "If the evidence cannot answer the question, reply exactly: ABSTAIN. "
                        "Never invent procedures, values, units, dates, or citations."
                    ),
                    temperature=0.1,
                    max_output_tokens=800,
                ),
            )
        except ProductionDependencyError:
            raise
        except Exception as exc:
            raise ProductionServiceError("The configured LLM provider failed to answer.") from exc

        answer = str(getattr(response, "text", "") or "").strip()
        usage = self._usage(response)
        if not answer or self._contains_abstention(answer):
            return AnswerDraft(
                answer=ABSTENTION_TEXT,
                abstained=True,
                citations=[],
                grounding='no_match',
                usage=usage,
            )

        citations = [
            Citation(
                chunk_id=candidate.chunk.chunk_id,
                doc_id=candidate.chunk.doc_id,
                source_name=candidate.chunk.source_name,
                source_path=candidate.chunk.source_path,
                page=candidate.chunk.page,
                pages=candidate.chunk.pages,
                region=candidate.chunk.region,
                region_type=candidate.chunk.region_type,
                provenance=candidate.chunk.provenance,
                quote=candidate.chunk.content[:500],
                score=candidate.rerank_score or candidate.hybrid_score,
            )
            for candidate in self._citation_candidates(
                answer,
                results[: self.settings.rerank_limit],
            )
        ]
        return AnswerDraft(
            answer=answer,
            abstained=False,
            citations=citations,
            grounding='grounded',
            usage=usage,
        )

    @staticmethod
    def _citation_candidates(
        answer: str,
        candidates: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Keep citations tied to words present in the generated answer.

        The provider receives several evidence chunks, but returning every
        reranked chunk as a citation makes the UI imply support the answer may
        not have used. A small lexical relevance filter keeps the citation set
        conservative and falls back to the best chunk when the answer is a
        paraphrase with no shared tokens.
        """
        if not candidates:
            return []

        answer_tokens = set(re.findall(r"[^\W_]+", answer.casefold()))
        scored = [
            (
                len(answer_tokens & set(re.findall(r"[^\W_]+", candidate.chunk.content.casefold())))
                / max(1, len(answer_tokens)),
                candidate,
            )
            for candidate in candidates
        ]
        best_relevance = max(score for score, _ in scored)
        if best_relevance <= 0:
            return [candidates[0]]

        cutoff = max(0.1, best_relevance * 0.5)
        selected = [candidate for score, candidate in scored if score >= cutoff]
        return selected or [candidates[0]]

    @staticmethod
    def _contains_abstention(answer: str) -> bool:
        lowered = answer.casefold()
        return lowered == 'abstain' or "i don't know" in lowered or "insufficient evidence" in lowered

    def _usage(self, response: Any) -> TokenUsage:
        metadata = getattr(response, 'usage_metadata', None)
        prompt = int(getattr(metadata, 'prompt_token_count', 0) or 0)
        completion = int(getattr(metadata, 'candidates_token_count', 0) or 0)
        total = int(getattr(metadata, 'total_token_count', prompt + completion) or prompt + completion)
        cost = (
            prompt * self.settings.input_usd_per_million
            + completion * self.settings.output_usd_per_million
        ) / 1_000_000
        return TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            estimated_cost_usd=cost,
        )



def chunks_from_docling(
    document_id: str,
    source_name: str,
    modality: str,
    records: Iterable[IngestedChunk],
    *,
    source_path: str = "",
    language: str = "multilingual",
) -> list[Chunk]:
    """Map Docling output into the API's stable chunk contract."""
    chunks: list[Chunk] = []
    for record in records:
        content = record.text.strip()
        if not content:
            continue
        heading = " > ".join(record.headings)
        caption = "; ".join(record.captions)
        pages = tuple(record.page_numbers)
        provenance = tuple(
            ChunkProvenance(
                ref=item.ref,
                kind=item.kind,
                page=item.page,
                bbox=item.bbox,
                coord_origin=item.coord_origin,
                confidence=item.confidence,
                review_required=item.review_required,
            )
            for item in record.provenance
        )
        region_type = provenance[0].kind if provenance else "document"
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:chunk-{record.chunk_index:04d}",
                doc_id=document_id,
                source_name=source_name,
                content=content,
                language=language,
                modality=modality,
                source_path=source_path,
                page=pages[0] if pages else None,
                pages=pages,
                region=heading or caption or "document evidence",
                region_type=region_type,
                provenance=provenance,
            )
        )
    return chunks


class ProductionIngestionService:
    def __init__(
        self,
        retriever: ProductionHybridRetriever,
        chunker: DoclingHybridChunkerAdapter | None = None,
        review_store: LifecycleStore | None = None,
    ) -> None:
        self.retriever = retriever
        self.chunker = chunker or DoclingHybridChunkerAdapter()
        self.review_store = review_store

    def ingest(
        self,
        source: Path,
        document_id: str,
        source_name: str,
        *,
        job_id: str | None = None,
        source_path: str | None = None,
        modality: str | None = None,
        language: str = "multilingual",
        progress_callback: StageCallback | None = None,
    ) -> dict[str, object]:
        records = self.chunker.convert_and_chunk(source, progress_callback=progress_callback)
        chunks = chunks_from_docling(
            document_id=document_id,
            source_name=source_name,
            modality=modality or source.suffix.casefold().lstrip(".") or "document",
            records=records,
            source_path=source_path or source.name,
            language=language,
        )
        indexed = self.retriever.upsert_chunks(chunks, progress_callback=progress_callback)
        review_items: list[dict[str, object]] = []
        for record in records:
            chunk_id = f'{document_id}:chunk-{record.chunk_index:04d}'
            for candidate in record.review_candidates:
                item = {
                    'job_id': job_id,
                    'document_id': document_id,
                    'chunk_id': chunk_id,
                    'source_ref': candidate.ref,
                    'kind': candidate.kind,
                    'page': candidate.page,
                    'bbox': candidate.bbox,
                    'confidence': candidate.confidence,
                    'reason': candidate.reason,
                }
                if self.review_store is not None:
                    review_items.append(
                        self.review_store.add_review_item(
                            job_id=job_id,
                            document_id=document_id,
                            chunk_id=chunk_id,
                            source_ref=candidate.ref,
                            kind=candidate.kind,
                            page=candidate.page,
                            bbox=candidate.bbox,
                            confidence=candidate.confidence,
                            reason=candidate.reason,
                        )
                    )
                else:
                    review_items.append(item)
        document = summarize_document(
            source=source,
            doc_id=document_id,
            source_name=source_name,
            source_path=source_path or source.name,
            file_format=source.suffix.casefold().lstrip('.') or 'document',
            modality=modality or source.suffix.casefold().lstrip('.') or 'document',
            language=language,
            factory_topic='uploaded document',
            chunks=chunks,
        )
        return {
            'review_items': review_items,
            'document': document,
            'chunks': chunks,
            "backend": "docling-hybridchunker",
            "chunk_count": indexed,
            "document_id": document_id,
        }
