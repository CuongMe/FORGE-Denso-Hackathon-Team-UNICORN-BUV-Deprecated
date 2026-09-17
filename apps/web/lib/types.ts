export type ChunkProvenance = {
  ref: string;
  kind: string;
  page: number | null;
  bbox: [number, number, number, number] | null;
  coord_origin: string | null;
};

export type Citation = {
  chunk_id: string;
  doc_id: string;
  source_name: string;
  source_path: string;
  page: number | null;
  pages: number[];
  region: string;
  region_type: string;
  provenance: ChunkProvenance[];
  quote: string;
  score: number;
};

export type QueryResponse = {
  answer: string;
  abstained: boolean;
  grounding: 'grounded' | 'best_match' | 'no_match';
  citations: Citation[];
  trace: {
    retrieval_mode: "hybrid";
    candidates_considered: number;
    reranked_count: number;
    reranker: string;
    evidence_threshold: number;
    latency_ms: number;
    candidates: RetrievalCandidate[];
  };
};

export type RetrievalCandidate = {
  hybrid_rank: number;
  rerank_rank: number | null;
  chunk_id: string;
  doc_id: string;
  source_name: string;
  source_path: string;
  page: number | null;
  pages: number[];
  region: string;
  region_type: string;
  provenance: ChunkProvenance[];
  lexical_score: number | null;
  semantic_score: number | null;
  hybrid_score: number;
  rerank_score: number | null;
  selected_for_answer: boolean;
};

export type HealthResponse = {
  status: string;
  ready: boolean;
  readiness: { ready: boolean; checks: Record<string, string> };
  demo_mode: boolean;
  documents_count: number;
  chunks_count: number;
  reranker: string;
  ingestion: {
    backend: string;
    docling_available: boolean;
    chunker: string;
    supported_extensions: string[];
  };
  graph?: {
    backend: string;
    available: boolean;
    nodes_count: number;
    edges_count: number;
  };
};

export type GraphNode = {
  id: string;
  kind: 'source' | 'chunk' | 'concept';
  label: string;
  subtitle: string;
  doc_id?: string | null;
  source_name?: string | null;
  source_path?: string | null;
  format?: string | null;
  status?: string | null;
  factory_topic?: string | null;
  page?: number | null;
  pages: number[];
  region?: string | null;
  region_type?: string | null;
  preview?: string | null;
  provenance: ChunkProvenance[];
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relation: string;
  page?: number | null;
  region?: string | null;
  provenance_ref?: string | null;
  confidence: number;
};

export type GraphResponse = {
  backend: string;
  selected_node: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
};

export type DocumentSummary = {
  doc_id: string;
  source_name: string;
  format: string;
  modality: string;
  language: string;
  factory_topic: string;
  source_path: string;
  status: string;
  chunk_count: number;
  page_count: number;
  sheet_count: number;
  row_count: number;
  column_count: number;
  image_count: number;
  region_types: string[];
};

export type UploadResponse = {
  document_id: string;
  filename: string;
  status: string;
  message: string;
  job_id?: string;
  job?: IngestionJob;
};

export type IngestionStageStatus = 'pending' | 'started' | 'completed' | 'failed';

export type IngestionStage = {
  stage: string;
  label: string;
  status: IngestionStageStatus;
  progress: number;
  message: string;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
};

export type IngestionJob = {
  job_id: string;
  document_id: string;
  original_filename: string;
  status: "queued" | "processing" | "indexed" | "failed";
  stage: string;
  attempts: number;
  error: string | null;
  result: { chunk_count?: number; review_count?: number } | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  progress: number;
  stages: IngestionStage[];
  document?: DocumentSummary | null;
};
