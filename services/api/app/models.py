from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChunkProvenance(BaseModel):
    """A source region carried from Docling into retrieval and citations."""

    ref: str
    kind: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    coord_origin: str | None = None


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_name: str
    content: str
    language: str
    modality: str
    source_path: str = ""
    page: int | None = None
    pages: tuple[int, ...] = ()
    region: str = "document evidence"
    region_type: str = "document"
    provenance: tuple[ChunkProvenance, ...] = ()


class RetrievedChunk(BaseModel):
    chunk: Chunk
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    rerank_score: float | None = None


class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    source_name: str
    source_path: str = ""
    page: int | None = None
    pages: tuple[int, ...] = ()
    region: str
    region_type: str = "document"
    provenance: tuple[ChunkProvenance, ...] = ()
    quote: str
    score: float


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("question must contain text")
        return cleaned


class RetrievalTrace(BaseModel):
    retrieval_mode: Literal["hybrid"] = "hybrid"
    candidates_considered: int
    reranked_count: int
    reranker: str
    evidence_threshold: float
    latency_ms: float


class QueryResponse(BaseModel):
    answer: str
    abstained: bool
    citations: list[Citation]
    trace: RetrievalTrace
