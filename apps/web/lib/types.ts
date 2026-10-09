export type EvaluationDataset = 'golden' | 'abstention' | 'all';
export type EvaluationSummary = {
  completed: number;
  failed: number;
  source_recall: number | null;
  source_precision: number | null;
  hybrid_mrr: number | null;
  reranked_mrr: number | null;
  reranker_lift: number | null;
  citation_precision: number | null;
  answer_token_f1: number | null;
  required_fact_coverage: number | null;
  answerability_correct: number | null;
  answerability_f1: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
};
export type EvaluationCase = {
  case_id: string;
  question: string;
  reference_answer: string;
  required_facts: string[];
  gold_evidence: { doc_id: string; page: number | null; region: string; quote: string }[];
  answerable: boolean;
  question_type: string;
  language: string;
  verification_status: string;
  status: 'completed' | 'failed';
  latency_ms: number;
  error: string | null;
  response: QueryResponse | null;
  scores: (Pick<EvaluationSummary, 'source_recall' | 'source_precision' | 'hybrid_mrr' | 'reranked_mrr' | 'citation_precision' | 'answer_token_f1' | 'required_fact_coverage'> & { answerability_correct: boolean; predicted_answerable: boolean }) | null;
};
export type EvaluationRun = {
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'interrupted' | 'failed';
  dataset: EvaluationDataset;
  total: number;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  dataset_hash: string;
  configuration: Record<string, unknown>;
  summary: EvaluationSummary;
  results?: EvaluationCase[];
};
export type QueryMetrics = {
  total_queries: number;
  window_size: number;
  retention_days: number;
  success_rate: number | null;
  abstention_rate: number | null;
  citation_rate: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  recent: { id: number | string; created_at: string; latency_ms: number; succeeded: number; abstained: number; citations: number; prompt_tokens: number; completion_tokens: number; total_tokens: number; estimated_cost_usd: number | null }[];
};

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
  parent_id?: string | null;
  parent_title?: string | null;
};

export type AggregationSummary = {
  operation: 'count' | 'sum' | 'average' | 'min' | 'max';
  value: number;
  source_doc_id: string;
  source_name: string;
  column: string | null;
  filter_text: string | null;
  rows_considered: number;
  rows_matched: number;
};

export type QueryResponse = {
  answer: string;
  abstained: boolean;
  grounding: 'grounded' | 'best_match' | 'no_match';
  citations: Citation[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number | null;
  };
  trace: {
    retrieval_mode: "hybrid" | "bm25";
    candidates_considered: number;
    reranked_count: number;
    reranker: string;
    evidence_threshold: number;
    latency_ms: number;
    candidates: RetrievalCandidate[];
    route: 'rag' | 'aggregation' | 'visual';
    cache_hit: boolean;
    request_id: string | null;
    prompt_version: string;
  };
  aggregation?: AggregationSummary | null;
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
  parent_id?: string | null;
  parent_title?: string | null;
  child_index?: number | null;
};

export type HealthResponse = {
  status: string;
  ready: boolean;
  readiness: { ready: boolean; checks: Record<string, string> };
  documents_count: number;
  chunks_count: number;
  reranker: string;
  ingestion: {
    backend: string;
    docling_available: boolean;
    chunker: string;
    supported_extensions: string[];
  };
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

export type DocumentChunkPreview = {
  chunk_id: string;
  content: string;
  page: number | null;
  pages: number[];
  region: string;
  region_type: string;
};

export type UploadResponse = {
  document_id: string;
  filename: string;
  status: string;
  message: string;
  job_id: string;
  job: IngestionJob;
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
