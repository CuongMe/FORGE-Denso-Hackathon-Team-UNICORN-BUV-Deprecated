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
  citations: Citation[];
  trace: {
    retrieval_mode: "hybrid";
    candidates_considered: number;
    reranked_count: number;
    reranker: string;
    evidence_threshold: number;
    latency_ms: number;
  };
};

export type HealthResponse = {
  status: string;
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
};

export type DocumentSummary = {
  doc_id: string;
  source_name: string;
  format: string;
  modality: string;
  language: string;
  factory_topic: string;
};

export type UploadResponse = {
  document_id: string;
  filename: string;
  status: string;
  message: string;
};
