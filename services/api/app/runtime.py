from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.corpus import list_demo_documents, load_source_pack_chunks
from app.document_metadata import summarize_document
from app.generation import AnswerDraft
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
from app.visual import Florence2VisualDescriber, GeminiVisualDescriber


PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.webp', '.bmp'})
IMAGE_QUERY_TERMS = frozenset({
    'image',
    'images',
    'img',
    'photo',
    'photos',
    'picture',
    'pictures',
    'screenshot',
    'screenshots',
    'visual',
    'visuals',
    'ảnh',
    'hình',
    'hinh',
})


def _query_requests_image_sources(question: str) -> bool:
    tokens = set(re.findall(r'\w+', question.casefold(), flags=re.UNICODE))
    return bool(tokens & IMAGE_QUERY_TERMS)


def _is_image_chunk(chunk: Chunk) -> bool:
    source = Path(chunk.source_path or chunk.source_name)
    if source.suffix.casefold() in IMAGE_EXTENSIONS:
        return True
    modality = chunk.modality.casefold()
    return any(term in modality for term in ('image', 'screenshot', 'photo', 'picture', 'visual'))


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
    chunks: tuple[Chunk, ...]
    retriever: Any
    reranker: Any
    answerer: Any
    ingestion_service: Any | None = None
    state_store: LifecycleStore | None = None
    _documents: list[dict[str, object]] = field(default_factory=list)
    _warm_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _models_warmed: bool = field(default=False, init=False, repr=False)

    @property
    def chunks_count(self) -> int:
        if self.state_store is not None:
            return self.state_store.indexed_counts()[1]
        return 0

    def document_list(self) -> list[dict[str, object]]:
        if self.state_store is not None:
            return self.state_store.list_documents()
        return list(self._documents)

    def ingestion(self) -> dict[str, object]:
        status = ingestion_status()
        status.update(
            {
                'mode': 'production',
                'backend': 'docling-hybridchunker',
                'qdrant_collection': self.ingestion_service.retriever.settings.collection_name,
                'state_store': 'sqlite',
                'state_database': self.state_store.database if self.state_store else None,
            }
        )
        return status

    def warm_models(self) -> None:
        """Load query and embedding models before accepting user work.

        Visual models remain lazy because many documents have no visual
        regions, and a missing optional visual model must not break text
        queries or embedding.
        """
        with self._warm_lock:
            if self._models_warmed:
                return
            for component in (self.retriever, self.reranker, self.answerer):
                warm = getattr(component, 'warm', None)
                if callable(warm):
                    warm()
            self._models_warmed = True

    def execute_query(
        self,
        question: str,
        *,
        document_id: str | None = None,
    ) -> QueryExecution:
        self.warm_models()
        retrieval_limit = getattr(getattr(self.retriever, 'settings', None), 'retrieval_limit', 8)
        if document_id:
            candidates = self.retriever.search(
                question,
                limit=retrieval_limit,
                document_id=document_id,
            )
        else:
            candidates = self.retriever.search(question, limit=retrieval_limit)
        if _query_requests_image_sources(question):
            candidates = self._image_candidates(candidates, document_id=document_id)
        ranked = self.reranker.rerank(
            question,
            candidates,
            limit=getattr(getattr(self.reranker, 'settings', None), 'rerank_limit', 5),
        )
        if document_id:
            ranked = self._apply_document_reference_match(ranked, document_id)
        return QueryExecution(
            candidates=candidates,
            ranked=ranked,
            draft=self.answerer.answer(question, ranked),
        )

    @staticmethod
    def _apply_document_reference_match(
        ranked: list[RetrievedChunk],
        document_id: str,
    ) -> list[RetrievedChunk]:
        """Treat an explicit source reference as an exact document match.

        The cross-encoder still ranks chunks within the referenced document, but
        its semantic score must not reject an operator-selected source merely
        because a generic question does not overlap the source text.
        """
        return [
            candidate.model_copy(update={'rerank_score': 1.0})
            if getattr(getattr(candidate, 'chunk', None), 'doc_id', None) == document_id
            else candidate
            for candidate in ranked
        ]

    def _image_candidates(
        self,
        candidates: list[RetrievedChunk],
        *,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Keep image questions grounded in image-backed chunks only.

        The source rail is metadata-driven, while retrieval is chunk-text-driven.
        Without this boundary, a query containing "list" can select an unrelated
        table or PDF when the requested image terms are absent from OCR text.
        """
        image_candidates = [candidate for candidate in candidates if _is_image_chunk(candidate.chunk)]
        chunk_ids_present = {candidate.chunk.chunk_id for candidate in image_candidates}
        representative_documents: set[str] = set()
        for chunk in self.chunks:
            if not _is_image_chunk(chunk) or chunk.doc_id in representative_documents:
                continue
            if document_id is not None and chunk.doc_id != document_id:
                continue
            representative_documents.add(chunk.doc_id)
            if chunk.chunk_id in chunk_ids_present:
                continue
            image_candidates.append(
                RetrievedChunk(
                    chunk=chunk,
                    hybrid_score=0.0,
                )
            )
            chunk_ids_present.add(chunk.chunk_id)
        return image_candidates

    def readiness(self) -> dict[str, object]:
        checks: dict[str, str] = {}
        try:
            self.warm_models()
            checks['models'] = 'ready'
        except (ProductionDependencyError, ProductionServiceError) as exc:
            checks['models'] = str(exc)
        except Exception:
            checks['models'] = 'model warm-up failed'
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
        ingested_chunks = [item for item in result.get('chunks', []) if isinstance(item, Chunk)]
        if ingested_chunks:
            self.chunks = (*self.chunks, *ingested_chunks)
        self._documents.append(document)
        return result


def build_runtime() -> RuntimeBundle:
    configured_mode = os.getenv('FORGE_RUNTIME_MODE', 'production').strip().casefold()
    if configured_mode != 'production':
        raise RuntimeError('FORGE_RUNTIME_MODE must be production; the demo runtime has been removed.')
    settings = ProductionSettings.from_env()
    include_source_pack = os.getenv('FORGE_INCLUDE_SOURCE_PACK', '1').strip().casefold() not in {
        '0', 'false', 'no', 'off'
    }
    chunks = tuple(load_source_pack_chunks()) if include_source_pack else ()
    state_store = LifecycleStore()
    state_store.initialize()
    state_store.requeue_processing_jobs()
    source_documents = list_demo_documents(list(chunks)) if include_source_pack else []
    state_store.sync_documents(source_documents)
    retriever = ProductionHybridRetriever(settings)
    if settings.visual_provider == 'florence2':
        visual_describer = Florence2VisualDescriber(model=settings.visual_model)
    elif settings.visual_provider == 'gemini':
        visual_describer = GeminiVisualDescriber(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        )
    else:
        raise RuntimeError(
            'FORGE_VISUAL_PROVIDER must be either florence2 or gemini.'
        )
    ingestion_service = ProductionIngestionService(
        retriever,
        chunker=DoclingHybridChunkerAdapter(visual_describer=visual_describer),
        review_store=state_store,
    )
    production_reranker = ProductionCrossEncoderReranker(settings)
    production_answerer = GeminiGroundedAnswerer(settings)
    return RuntimeBundle(
        chunks=chunks,
        retriever=retriever,
        reranker=production_reranker,
        answerer=production_answerer,
        ingestion_service=ingestion_service,
        state_store=state_store,
        _documents=source_documents,
    )
