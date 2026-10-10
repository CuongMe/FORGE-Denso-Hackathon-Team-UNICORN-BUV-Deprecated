from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChunkProvenance(BaseModel):
    ref: str
    kind: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    coord_origin: str | None = None
    confidence: float | None = None
    review_required: bool = False


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_name: str
    content: str
    language: str
    modality: str
    source_path: str = ''
    page: int | None = None
    pages: tuple[int, ...] = ()
    region: str = 'document evidence'
    region_type: str = 'document'
    provenance: tuple[ChunkProvenance, ...] = ()
    parent_id: str | None = None
    parent_title: str | None = None
    child_index: int | None = None


class RetrievedChunk(BaseModel):
    chunk: Chunk
    lexical_score: float | None = None
    semantic_score: float | None = None
    hybrid_score: float
    rerank_score: float | None = None


class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    source_name: str
    source_path: str = ''
    page: int | None = None
    pages: tuple[int, ...] = ()
    region: str
    region_type: str = 'document'
    provenance: tuple[ChunkProvenance, ...] = ()
    quote: str
    score: float
    parent_id: str | None = None
    parent_title: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)

    @field_validator('question')
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        cleaned = ' '.join(value.split())
        if not cleaned:
            raise ValueError('question must contain text')
        return cleaned


class RetrievalCandidate(BaseModel):
    hybrid_rank: int
    rerank_rank: int | None = None
    chunk_id: str
    doc_id: str
    source_name: str
    source_path: str = ''
    page: int | None = None
    pages: tuple[int, ...] = ()
    region: str = 'document evidence'
    region_type: str = 'document'
    provenance: tuple[ChunkProvenance, ...] = ()
    parent_id: str | None = None
    parent_title: str | None = None
    child_index: int | None = None
    lexical_score: float | None = None
    semantic_score: float | None = None
    hybrid_score: float
    rerank_score: float | None = None
    selected_for_answer: bool = False


class RetrievalTrace(BaseModel):
    retrieval_mode: Literal['hybrid'] = 'hybrid'
    candidates_considered: int
    reranked_count: int
    reranker: str
    evidence_threshold: float
    latency_ms: float
    retrieval_ms: float = Field(default=0.0, ge=0)
    rerank_ms: float = Field(default=0.0, ge=0)
    generation_ms: float = Field(default=0.0, ge=0)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    route: Literal['rag', 'aggregation', 'visual'] = 'rag'
    cache_hit: bool = False
    request_id: str | None = None
    prompt_version: str = 'grounded-answer-v3'


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)


class AggregationSummary(BaseModel):
    operation: Literal['count', 'sum', 'average', 'min', 'max']
    value: int | float
    source_doc_id: str
    source_name: str
    column: str | None = None
    filter_text: str | None = None
    rows_considered: int = Field(ge=0)
    rows_matched: int = Field(ge=0)


class QueryResponse(BaseModel):
    answer: str
    abstained: bool
    grounding: Literal['grounded', 'best_match', 'no_match'] = 'grounded'
    citations: list[Citation]
    trace: RetrievalTrace
    usage: TokenUsage = Field(default_factory=TokenUsage)
    aggregation: AggregationSummary | None = None


class IngestionStage(BaseModel):
    stage: str
    label: str
    status: Literal['pending', 'started', 'completed', 'failed']
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ''
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str


class ReviewDecision(BaseModel):
    status: Literal['pending', 'accepted', 'rejected']
    notes: str | None = Field(default=None, max_length=2000)
