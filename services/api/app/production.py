from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from app.generation import ABSTENTION_TEXT, AnswerDraft
from app.ingestion import DoclingHybridChunkerAdapter, IngestedChunk
from app.models import Chunk, ChunkProvenance, Citation, RetrievedChunk


DEFAULT_DENSE_MODEL = "BAAI/bge-m3"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_LLM_MODEL = "gemini-2.5-flash-lite"
class ProductionDependencyError(RuntimeError):
    """Raised when an explicitly selected production dependency is unavailable."""


class ProductionServiceError(RuntimeError):
    """Raised when a configured production service cannot complete an operation."""


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

    @classmethod
    def from_env(cls) -> "ProductionSettings":
        return cls(
            qdrant_url=os.getenv("FORGE_QDRANT_URL", "http://127.0.0.1:6333"),
            qdrant_api_key=os.getenv("FORGE_QDRANT_API_KEY") or None,
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
            retrieval_limit=max(1, int(os.getenv("FORGE_RETRIEVAL_LIMIT", "20"))),
            rerank_limit=max(1, int(os.getenv("FORGE_RERANK_LIMIT", "5"))),
            evidence_threshold=float(os.getenv("FORGE_EVIDENCE_THRESHOLD", "0.45")),
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
                self._dense_encoder = SentenceTransformer(self.settings.dense_model)
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

    @property
    def client(self) -> Any:
        self._load_dependencies()
        return self._client

    def _encode_documents(self, texts: list[str]) -> list[list[float]]:
        self._load_dependencies()
        encoder = self._dense_encoder
        method = getattr(encoder, "encode_document", None) or getattr(encoder, "encode")
        try:
            encoded = method(texts, normalize_embeddings=True, show_progress_bar=False)
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
            embeddings = list(self._sparse_encoder.embed(texts, batch_size=max(1, len(texts))))
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

    def upsert_chunks(self, chunks: Iterable[Chunk]) -> int:
        records = list(chunks)
        if not records:
            return 0
        self.ensure_collection()
        texts = [record.content for record in records]
        dense_vectors = self._encode_documents(texts)
        sparse_vectors = self._encode_sparse(texts)
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
        try:
            self.client.upsert(
                collection_name=self.settings.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            raise ProductionServiceError("Qdrant rejected the chunk upsert.") from exc
        return len(points)

    def search(self, question: str, limit: int = 8) -> list[RetrievedChunk]:
        if limit < 1:
            return []
        self.ensure_collection()
        dense_query = self._encode_query(question)
        sparse_query = self._sparse_vector(self._encode_sparse([question])[0])
        prefetch_limit = max(limit * 4, 20)
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
                    lexical_score=score,
                    semantic_score=score,
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
                self._model = CrossEncoder(self.settings.reranker_model, max_length=512)
            except Exception as exc:
                raise ProductionServiceError(
                    f"The reranker model could not be loaded: {self.settings.reranker_model}."
                ) from exc
        return self._model

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

    def answer(self, question: str, results: list[RetrievedChunk]) -> AnswerDraft:
        if not results:
            return self._abstention()
        best_score = results[0].rerank_score
        if best_score is None or best_score < self.evidence_threshold:
            return self._abstention()

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
                        "If the evidence does not directly support an answer, respond exactly: "
                        f"{ABSTENTION_TEXT} "
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
        if not answer or self._contains_abstention(answer):
            return self._abstention()

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
            for candidate in results[: self.settings.rerank_limit]
        ]
        return AnswerDraft(answer=answer, abstained=False, citations=citations)

    @staticmethod
    def _contains_abstention(answer: str) -> bool:
        lowered = answer.casefold()
        return "i don't know" in lowered or "insufficient evidence" in lowered

    @staticmethod
    def _abstention() -> AnswerDraft:
        return AnswerDraft(answer=ABSTENTION_TEXT, abstained=True, citations=[])


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
    ) -> None:
        self.retriever = retriever
        self.chunker = chunker or DoclingHybridChunkerAdapter()

    def ingest(
        self,
        source: Path,
        document_id: str,
        source_name: str,
        *,
        source_path: str | None = None,
        modality: str | None = None,
        language: str = "multilingual",
    ) -> dict[str, object]:
        records = self.chunker.convert_and_chunk(source)
        chunks = chunks_from_docling(
            document_id=document_id,
            source_name=source_name,
            modality=modality or source.suffix.casefold().lstrip(".") or "document",
            records=records,
            source_path=source_path or source.name,
            language=language,
        )
        indexed = self.retriever.upsert_chunks(chunks)
        return {
            "backend": "docling-hybridchunker",
            "chunk_count": indexed,
            "document_id": document_id,
        }
