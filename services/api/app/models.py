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
    candidates: list[RetrievalCandidate] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    abstained: bool
    grounding: Literal['grounded', 'best_match', 'no_match'] = 'grounded'
    citations: list[Citation]
    trace: RetrievalTrace


class GraphNode(BaseModel):
    id: str
    kind: Literal['source', 'chunk', 'concept']
    label: str
    subtitle: str = ''
    doc_id: str | None = None
    source_name: str | None = None
    source_path: str | None = None
    format: str | None = None
    status: str | None = None
    factory_topic: str | None = None
    page: int | None = None
    pages: list[int] = Field(default_factory=list)
    region: str | None = None
    region_type: str | None = None
    preview: str | None = None
    provenance: list[ChunkProvenance] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    page: int | None = None
    region: str | None = None
    provenance_ref: str | None = None
    confidence: float = 0.0


class GraphResponse(BaseModel):
    backend: str
    selected_node: str | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0


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
