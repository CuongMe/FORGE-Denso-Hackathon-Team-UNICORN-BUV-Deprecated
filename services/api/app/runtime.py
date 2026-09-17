from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.corpus import list_demo_documents, load_source_pack_chunks
from app.document_metadata import summarize_document
from app.generation import AnswerDraft, GroundedAnswerer
from app.graph_store import GraphStoreUnavailable, KuzuGraphStore
from app.ingestion import DoclingHybridChunkerAdapter, ingestion_status
from app.models import Chunk, RetrievedChunk
from app.persistence import LifecycleStore, sha256_file
from app.pipeline import StageCallback
from app.production import (
    GeminiGroundedAnswerer,
    ProductionDependencyError,
    ProductionCrossEncoderReranker,
    ProductionHybridRetriever,
    ProductionIngestionService,
    ProductionServiceError,
    ProductionSettings,
)
from app.retrieval import CrossEncoderReranker, HybridRetriever
from app.visual import GeminiVisualDescriber


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class QueryExecution:
    candidates: list[RetrievedChunk]
    ranked: list[RetrievedChunk]
    draft: AnswerDraft


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
    state_store: LifecycleStore | None = None
    graph_store: KuzuGraphStore | None = None
    _documents: list[dict[str, object]] = field(default_factory=list)
    _indexed_chunks: int = 0

    @property
    def demo_mode(self) -> bool:
        return self.mode == 'demo'

    @property
    def chunks_count(self) -> int:
        if self.state_store is not None:
            return self.state_store.indexed_counts()[1]
        return len(self.chunks) + self._indexed_chunks

    def document_list(self) -> list[dict[str, object]]:
        if self.demo_mode:
            return list_demo_documents(list(self.chunks))
        if self.state_store is not None:
            return self.state_store.list_documents()
        return list(self._documents)

    def ingestion(self) -> dict[str, object]:
        status = ingestion_status()
        status.update({'mode': self.mode})
        if self.mode == 'production':
            status.update(
                {
                    'backend': 'docling-hybridchunker',
                    'qdrant_collection': self.ingestion_service.retriever.settings.collection_name,
                    'state_store': 'sqlite',
                    'state_database': self.state_store.database if self.state_store else None,
                }
            )
        return status

    def graph_status(self) -> dict[str, object]:
        if self.graph_store is None:
            return {
                'backend': 'unavailable',
                'available': False,
                'nodes_count': 0,
                'edges_count': 0,
            }
        return self.graph_store.status()

    def execute_query(self, question: str) -> QueryExecution:
        candidates = self.retriever.search(
            question,
            limit=getattr(getattr(self.retriever, 'settings', None), 'retrieval_limit', 8),
        )
        ranked = self.reranker.rerank(
            question,
            candidates,
            limit=getattr(getattr(self.reranker, 'settings', None), 'rerank_limit', 5),
        )
        return QueryExecution(
            candidates=candidates,
            ranked=ranked,
            draft=self.answerer.answer(question, ranked),
        )

    def readiness(self) -> dict[str, object]:
        if self.demo_mode:
            return {'ready': True, 'checks': {'corpus': 'ready', 'retrieval': 'demo', 'generation': 'demo'}}

        checks: dict[str, str] = {}
        for name, check in (
            ('qdrant', self.retriever.ensure_collection),
            ('reranker', lambda: self.reranker.model),
            ('generator', lambda: self.answerer.client),
        ):
            try:
                check()
                checks[name] = 'ready'
            except (ProductionDependencyError, ProductionServiceError) as exc:
                checks[name] = str(exc)
            except Exception:
                checks[name] = 'provider check failed'
        if self.state_store is None:
            checks['index'] = 'state store unavailable'
        else:
            snapshot = self.state_store.get_index_snapshot()
            indexed_documents, indexed_chunks = self.state_store.indexed_counts()
            expected_documents = len(self.state_store.list_documents())
            collection_name = self.ingestion_service.retriever.settings.collection_name
            if snapshot is None:
                checks['index'] = 'not indexed'
            elif snapshot['collection_name'] != collection_name:
                checks['index'] = 'collection snapshot mismatch'
            elif indexed_documents != expected_documents:
                checks['index'] = 'documents pending indexing'
            elif indexed_chunks != snapshot['indexed_chunks']:
                checks['index'] = 'index snapshot is stale'
            else:
                try:
                    points = self.retriever.count_points()
                    checks['index'] = 'ready' if points == indexed_chunks else 'qdrant point count mismatch'
                except (ProductionDependencyError, ProductionServiceError) as exc:
                    checks['index'] = str(exc)
        return {'ready': all(value == 'ready' for value in checks.values()), 'checks': checks}

    def refresh_index_snapshot(self) -> None:
        if self.state_store is None or self.ingestion_service is None:
            return
        indexed_documents, indexed_chunks = self.state_store.indexed_counts()
        corpus_version = self.state_store.indexed_corpus_version()
        self.state_store.set_index_snapshot(
            collection_name=self.ingestion_service.retriever.settings.collection_name,
            corpus_version=corpus_version,
            indexed_documents=indexed_documents,
            indexed_chunks=indexed_chunks,
        )

    def ingest(
        self,
        source: Path,
        document_id: str,
        source_name: str,
        *,
        job_id: str | None = None,
        progress_callback: StageCallback | None = None,
    ) -> dict[str, object]:
        if self.ingestion_service is None:
            raise RuntimeError('Document ingestion is only available in production mode.')
        source_path = _relative_source_path(source)
        file_format = source.suffix.casefold().lstrip('.') or 'document'
        ingestion_kwargs: dict[str, object] = {'source_path': source_path}
        if job_id is not None:
            ingestion_kwargs['job_id'] = job_id
        if progress_callback is not None:
            ingestion_kwargs['progress_callback'] = progress_callback
        result = self.ingestion_service.ingest(
            source,
            document_id,
            source_name,
            **ingestion_kwargs,
        )
        chunk_count = int(result.get('chunk_count', 0))
        self._indexed_chunks += chunk_count
        document = result.get('document')
        if not isinstance(document, dict):
            document = summarize_document(
                source=source,
                doc_id=document_id,
                source_name=source_name,
                source_path=source_path,
                file_format=file_format,
                modality=file_format,
                language='multilingual',
                factory_topic='uploaded document',
                chunks=result.get('chunks', []),
            )
        if self.state_store is not None:
            self.state_store.upsert_document(
                document,
                content_hash=sha256_file(source),
                size_bytes=source.stat().st_size,
                status='indexed',
                ingestion_job_id=job_id,
            )
            self.refresh_index_snapshot()
        if progress_callback:
            progress_callback('graph_extraction', 'started', 0, 'Extracting document relationships into Kùzu.')
        if self.graph_store is not None:
            graph_chunks = [item for item in result.get('chunks', []) if isinstance(item, Chunk)]
            if graph_chunks:
                self.graph_store.sync_documents([document], graph_chunks)
            if progress_callback:
                progress_callback('graph_extraction', 'completed', 100, 'Document relationships indexed in Kùzu.')
        elif progress_callback:
            progress_callback('graph_extraction', 'completed', 100, 'Graph store unavailable; relationship indexing was skipped.')
        self._documents.append(document)
        return result


def build_runtime() -> RuntimeBundle:
    mode = os.getenv('FORGE_RUNTIME_MODE', 'demo').strip().casefold()
    if mode not in {'demo', 'production'}:
        raise RuntimeError('FORGE_RUNTIME_MODE must be either demo or production.')
    graph_store = _build_graph_store()
    if mode == 'demo':
        chunks = tuple(load_source_pack_chunks())
        documents = list_demo_documents(list(chunks))
        if graph_store is not None:
            graph_store.sync_documents(documents, chunks)
        return RuntimeBundle(
            mode='demo',
            chunks=chunks,
            retriever=HybridRetriever(chunks),
            reranker=CrossEncoderReranker(),
            answerer=GroundedAnswerer(),
            graph_store=graph_store,
        )

    settings = ProductionSettings.from_env()
    chunks = tuple(load_source_pack_chunks())
    state_store = LifecycleStore()
    state_store.initialize()
    state_store.requeue_processing_jobs()
    source_documents = list_demo_documents(list(chunks))
    state_store.sync_documents(source_documents)
    retriever = ProductionHybridRetriever(settings)
    visual_describer = GeminiVisualDescriber(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
    )
    ingestion_service = ProductionIngestionService(
        retriever,
        chunker=DoclingHybridChunkerAdapter(visual_describer=visual_describer),
        review_store=state_store,
    )
    production_reranker = ProductionCrossEncoderReranker(settings)
    production_answerer = GeminiGroundedAnswerer(settings)
    return RuntimeBundle(
        mode='production',
        chunks=chunks,
        retriever=retriever,
        reranker=production_reranker,
        answerer=production_answerer,
        ingestion_service=ingestion_service,
        state_store=state_store,
        graph_store=graph_store,
        _documents=source_documents,
    )


def _build_graph_store() -> KuzuGraphStore | None:
    configured_path = os.getenv('FORGE_GRAPH_DB_PATH', '').strip()
    database_path = Path(configured_path) if configured_path else PROJECT_ROOT / 'data' / 'state' / 'forge.kuzu'
    try:
        return KuzuGraphStore(database_path)
    except GraphStoreUnavailable:
        return None
