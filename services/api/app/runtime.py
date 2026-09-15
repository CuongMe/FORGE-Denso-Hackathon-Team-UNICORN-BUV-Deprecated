from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.corpus import list_demo_documents, load_source_pack_chunks
from app.generation import GroundedAnswerer
from app.ingestion import ingestion_status
from app.models import Chunk
from app.production import (
    GeminiGroundedAnswerer,
    ProductionCrossEncoderReranker,
    ProductionHybridRetriever,
    ProductionIngestionService,
    ProductionSettings,
)
from app.retrieval import CrossEncoderReranker, HybridRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _relative_source_path(source: Path) -> str:
    try:
        return source.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return source.name


@dataclass(slots=True)
class RuntimeBundle:
    mode: str
    chunks: tuple[Chunk, ...]
    retriever: Any
    reranker: Any
    answerer: Any
    ingestion_service: Any | None = None
    _documents: list[dict[str, str]] = field(default_factory=list)
    _indexed_chunks: int = 0

    @property
    def demo_mode(self) -> bool:
        return self.mode == "demo"

    @property
    def chunks_count(self) -> int:
        return len(self.chunks) + self._indexed_chunks

    def document_list(self) -> list[dict[str, str]]:
        if self.demo_mode:
            return list_demo_documents()
        return list(self._documents)

    def ingestion(self) -> dict[str, object]:
        status = ingestion_status()
        status.update({"mode": self.mode})
        if self.mode == "production":
            status.update(
                {
                    "backend": "docling-hybridchunker",
                    "qdrant_collection": self.ingestion_service.retriever.settings.collection_name,
                }
            )
        return status

    def ingest(self, source: Path, document_id: str, source_name: str) -> dict[str, object]:
        if self.ingestion_service is None:
            raise RuntimeError("Document ingestion is only available in production mode.")
        source_path = _relative_source_path(source)
        file_format = source.suffix.casefold().lstrip(".") or "document"
        result = self.ingestion_service.ingest(
            source,
            document_id,
            source_name,
            source_path=source_path,
        )
        chunk_count = int(result.get("chunk_count", 0))
        self._indexed_chunks += chunk_count
        self._documents.append(
            {
                "doc_id": document_id,
                "source_name": source_name,
                "source_path": source_path,
                "format": file_format,
                "modality": file_format,
                "language": "multilingual",
                "factory_topic": "uploaded document",
            }
        )
        return result


def build_runtime() -> RuntimeBundle:
    mode = os.getenv("FORGE_RUNTIME_MODE", "demo").strip().casefold()
    if mode == "demo":
        chunks = tuple(load_source_pack_chunks())
        return RuntimeBundle(
            mode="demo",
            chunks=chunks,
            retriever=HybridRetriever(chunks),
            reranker=CrossEncoderReranker(),
            answerer=GroundedAnswerer(),
        )

    if mode != "production":
        raise RuntimeError("FORGE_RUNTIME_MODE must be either 'demo' or 'production'.")

    settings = ProductionSettings.from_env()
    retriever = ProductionHybridRetriever(settings)
    return RuntimeBundle(
        mode="production",
        chunks=(),
        retriever=retriever,
        reranker=ProductionCrossEncoderReranker(settings),
        answerer=GeminiGroundedAnswerer(settings),
        ingestion_service=ProductionIngestionService(retriever),
    )
