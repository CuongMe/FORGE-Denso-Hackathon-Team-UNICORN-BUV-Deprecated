from __future__ import annotations

import csv
import hashlib
import html
import re
import secrets
import mimetypes
import os
import time
import io
import zipfile
import logging
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from xml.etree import ElementTree

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.corpus import PROJECT_ROOT
from app.ingestion import SUPPORTED_INPUT_EXTENSIONS
from app.aggregation import aggregate_rows
from app.models import Citation, QueryRequest, QueryResponse, RetrievalCandidate, RetrievalTrace
from app.models import ReviewDecision
from app.observability import (
    bind_request_id,
    configure_json_logging,
    current_request_id,
    log_event,
    new_request_id,
    reset_request_id,
)
from app.persistence import LifecycleStore
from app.query_cache import build_cache_key
from app.query_router import QueryRoute, classify_query
from app.tabular import read_table_rows, read_table_sheets
from app.production import ProductionDependencyError, ProductionServiceError
from app.runtime import build_runtime
from app.worker import IngestionWorker
from app.evaluation import EvaluationStore, EvaluationWorker, evaluation_router


UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DOCUMENT_REFERENCE_PATTERN = re.compile(r'(?<!\S)@([A-Za-z0-9][A-Za-z0-9_-]*)')
FORGE_LOGGER = logging.getLogger('forge.api')
configure_json_logging()


def _relative_source_path(source: Path) -> str:
    try:
        return source.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return source.name


def _content_matches_extension(extension: str, data: bytes) -> bool:
    if extension == '.pdf':
        return data.startswith(b'%PDF-')
    if extension == '.png':
        return data.startswith(b'\x89PNG\r\n\x1a\n')
    if extension in {'.jpg', '.jpeg'}:
        return data.startswith(b'\xff\xd8\xff')
    if extension == '.bmp':
        return data.startswith(b'BM')
    if extension == '.webp':
        return len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    if extension == '.xlsx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
            return '[Content_Types].xml' in names and any(name.startswith('xl/') for name in names)
        except (OSError, ValueError, zipfile.BadZipFile):
            return False
    if extension == '.pptx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
            return '[Content_Types].xml' in names and 'ppt/presentation.xml' in names
        except (OSError, ValueError, zipfile.BadZipFile):
            return False
    if extension == '.xls':
        return data.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    if extension in {'.csv', '.txt'}:
        try:
            return '\x00' not in data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return False
    return False

runtime = None
evaluation_store: EvaluationStore | None = None
ingestion_worker: IngestionWorker | None = None
evaluation_worker: EvaluationWorker | None = None
_runtime_lock = threading.Lock()


def get_runtime():
    global runtime
    if runtime is None:
        with _runtime_lock:
            if runtime is None:
                runtime = build_runtime()
    return runtime


def get_evaluation_store() -> EvaluationStore:
    global evaluation_store
    if evaluation_store is None:
        active_runtime = get_runtime()
        if active_runtime.state_store is None:
            raise RuntimeError('Production runtime requires the durable lifecycle store.')
        evaluation_store = EvaluationStore(active_runtime.state_store.database)
        evaluation_store.initialize()
    return evaluation_store


class ReadinessCache:
    def __init__(self, max_age_seconds: float = 30.0) -> None:
        self.max_age_seconds = max(1.0, max_age_seconds)
        self._value: dict[str, object] = {
            'ready': False,
            'checks': {'providers': 'checking'},
        }
        self._updated_at = 0.0
        self._refreshing = False
        self._lock = threading.Lock()

    def snapshot(self, active_runtime) -> dict[str, object]:
        with self._lock:
            stale = time.monotonic() - self._updated_at >= self.max_age_seconds
            if stale and not self._refreshing:
                self._refreshing = True
                threading.Thread(
                    target=self._refresh,
                    args=(active_runtime,),
                    name='forge-readiness-refresh',
                    daemon=True,
                ).start()
            return {
                **self._value,
                'cached': True,
                'refreshing': self._refreshing,
                'max_age_seconds': self.max_age_seconds,
            }

    def _refresh(self, active_runtime) -> None:
        try:
            value = active_runtime.readiness()
        except Exception:
            logging.getLogger(__name__).exception('Readiness refresh failed')
            value = {'ready': False, 'checks': {'providers': 'check failed'}}
        with self._lock:
            self._value = value
            self._updated_at = time.monotonic()
            self._refreshing = False


readiness_cache = ReadinessCache(
    float(os.getenv('FORGE_READINESS_CACHE_SECONDS', '30'))
)


@asynccontextmanager
async def lifespan(_app):
    global ingestion_worker, evaluation_worker
    active_runtime = get_runtime()
    warm_models = getattr(active_runtime, 'warm_models', None)
    if callable(warm_models):
        def warm_in_background() -> None:
            started = time.perf_counter()
            try:
                warm_models()
            except Exception:
                logging.getLogger(__name__).warning(
                    'FORGE model warm-up did not complete in %.2fs; '
                    'the first request may retry model loading.',
                    time.perf_counter() - started,
                    exc_info=True,
                )
            else:
                logging.getLogger(__name__).info(
                    'FORGE model warm-up completed in %.2fs',
                    time.perf_counter() - started,
                )

        threading.Thread(
            target=warm_in_background,
            name='forge-model-warmup',
            daemon=True,
        ).start()
    get_evaluation_store()
    readiness_cache.snapshot(active_runtime)
    if active_runtime.state_store is None:
        raise RuntimeError('Production runtime requires the durable lifecycle store.')
    ingestion_worker = IngestionWorker(active_runtime, active_runtime.state_store)
    evaluation_worker = EvaluationWorker(get_evaluation_store(), _execute_query)
    ingestion_worker.start()
    evaluation_worker.start()
    try:
        yield
    finally:
        ingestion_worker.stop()
        evaluation_worker.stop()
        ingestion_worker = None
        evaluation_worker = None

app = FastAPI(
    lifespan=lifespan,
    title="FORGE Factory Operations Retrieval API",
    version="0.1.0",
    description="Multimodal retrieval and grounded answer API for the FORGE demo.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FORGE_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    supplied_request_id = (request.headers.get("X-Request-ID") or "").strip()
    request_id = supplied_request_id[:128] if 0 < len(supplied_request_id) <= 128 else new_request_id()
    request.state.request_id = request_id
    request_token = bind_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            FORGE_LOGGER,
            "api_request_failed",
            request_id=request_id,
            method=request.method,
            route=request.url.path,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            exception=type(exc).__name__,
        )
        raise
    finally:
        reset_request_id(request_token)
    response.headers["X-Request-ID"] = request_id
    log_event(
        FORGE_LOGGER,
        "api_request_completed",
        request_id=request_id,
        method=request.method,
        route=request.url.path,
        status_code=response.status_code,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


def _error(code: str, message: str, status_code: int, details: object | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": jsonable_encoder(details)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    return _error("VALIDATION_ERROR", "The request could not be validated.", 422, exc.errors())


@app.exception_handler(HTTPException)
async def http_error_handler(_, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else None
    code = detail.get("code", "HTTP_ERROR") if detail else "HTTP_ERROR"
    message = detail.get("message", "The request could not be completed.") if detail else str(exc.detail)
    return _error(code, message, exc.status_code, detail.get("details") if detail else None)


@app.get("/api/health")
def health() -> dict[str, object]:
    active_runtime = get_runtime()
    readiness = readiness_cache.snapshot(active_runtime)
    return {
        'ready': readiness['ready'],
        'readiness': readiness,
        "status": "ok",
        "documents_count": len(active_runtime.document_list()),
        "chunks_count": active_runtime.chunks_count,
        "reranker": active_runtime.reranker.name,
        "ingestion": active_runtime.ingestion(),
    }


@app.get("/api/documents")
def documents() -> dict[str, object]:
    items = get_runtime().document_list()
    return {"data": items, "total": len(items)}

@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    started = time.perf_counter()
    response = None
    try:
        response = _execute_query(payload)
        return response
    finally:
        try:
            get_evaluation_store().record_query(round((time.perf_counter() - started) * 1000, 2), response)
        except sqlite3.Error:
            logging.getLogger(__name__).exception('Could not record query metrics')


def _split_document_reference(question: str) -> tuple[str, str | None]:
    """Remove the UI's @document-id token before semantic retrieval."""
    match = DOCUMENT_REFERENCE_PATTERN.search(question)
    if match is None:
        return question, None
    cleaned = DOCUMENT_REFERENCE_PATTERN.sub('', question, count=1).strip()
    return cleaned or 'Explain this source.', match.group(1)


def _resolve_project_source(source_path: str) -> Path | None:
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(PROJECT_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _tabular_source(active_runtime, question: str, document_id: str | None) -> dict[str, object] | None:
    documents = active_runtime.document_list()
    tabular = [
        item for item in documents
        if str(item.get('format') or '').casefold() in {'csv', 'xlsx', 'xls'}
        and str(item.get('status') or 'indexed').casefold() in {'indexed', 'ready'}
    ]
    if document_id:
        return next((item for item in tabular if item.get('doc_id') == document_id), None)
    if len(tabular) == 1:
        return tabular[0]
    lowered = question.casefold()
    named = [item for item in tabular if str(item.get('source_name') or '').casefold() in lowered]
    if len(named) == 1:
        return named[0]
    query_tokens = set(re.findall(r'\w+', lowered, flags=re.UNICODE))
    scored = []
    for item in tabular:
        source_tokens = set(re.findall(r'\w+', str(item.get('source_name') or '').casefold(), flags=re.UNICODE))
        overlap = len(query_tokens & source_tokens)
        if overlap:
            scored.append((overlap, item))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if len(scored) == 1 or scored[0][0] > scored[1][0] else None


def _query_cache_ttl_seconds() -> int:
    try:
        return max(1, int(os.getenv('FORGE_QUERY_CACHE_TTL_SECONDS', '900')))
    except ValueError:
        return 900


def _cache_query_response(
    active_runtime,
    cache_key: str,
    *,
    corpus_version: str,
    prompt_version: str,
    response: QueryResponse,
) -> None:
    if active_runtime.state_store is None:
        return
    active_runtime.state_store.put_query_cache(
        cache_key,
        corpus_version=corpus_version,
        prompt_version=prompt_version,
        response=response.model_dump(mode='json'),
        ttl_seconds=_query_cache_ttl_seconds(),
    )


def _aggregation_response(
    active_runtime,
    question: str,
    source: dict[str, object] | None,
    *,
    request_id: str | None,
    started: float,
) -> QueryResponse | None:
    if source is None:
        return None
    source_path = str(source.get('source_path') or '')
    path = _resolve_project_source(source_path)
    if path is None:
        return None
    try:
        rows = read_table_rows(path)
        result = aggregate_rows(
            question,
            rows,
            source_doc_id=str(source.get('doc_id') or ''),
            source_name=str(source.get('source_name') or path.name),
        )
    except (OSError, UnicodeError, csv.Error, KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    if result is None:
        return None
    prompt_version = getattr(active_runtime.answerer, 'prompt_version', 'grounded-answer-v3')
    citation = Citation(
        chunk_id=f"{source.get('doc_id')}:aggregate",
        doc_id=str(source.get('doc_id') or ''),
        source_name=str(source.get('source_name') or path.name),
        source_path=source_path,
        region='full table',
        region_type='table',
        quote=result.answer,
        score=1.0,
    )
    trace = RetrievalTrace(
        candidates_considered=0,
        reranked_count=0,
        reranker='not used (structured aggregation)',
        evidence_threshold=0.0,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        route='aggregation',
        request_id=request_id,
        prompt_version=prompt_version,
    )
    return QueryResponse(
        answer=result.answer,
        abstained=False,
        grounding='grounded',
        citations=[citation],
        trace=trace,
        aggregation=result.summary,
    )


def _execute_query(payload: QueryRequest, *, request_id: str | None = None) -> QueryResponse:
    active_runtime = get_runtime()
    request_id = request_id or current_request_id()
    started = time.perf_counter()
    try:
        question, document_id = _split_document_reference(payload.question)
        referenced = active_runtime.state_store.get_document(document_id) if document_id and active_runtime.state_store else None
        source = _tabular_source(active_runtime, question, document_id)
        route = classify_query(
            question,
            tabular_available=source is not None or any(
                str(item.get('format') or '').casefold() in {'csv', 'xlsx', 'xls'}
                for item in active_runtime.document_list()
            ),
            referenced_format=str(referenced.get('format') or '') if referenced else None,
        )
        prompt_version = getattr(active_runtime.answerer, 'prompt_version', 'grounded-answer-v3')
        corpus_version = active_runtime.state_store.indexed_corpus_version() if active_runtime.state_store else 'no-state'
        runtime_signature = '|'.join(
            str(value)
            for value in (
                getattr(active_runtime.reranker, 'name', ''),
                getattr(getattr(active_runtime.answerer, 'settings', None), 'llm_model', ''),
            )
        )
        cache_key = build_cache_key(
            question,
            document_id,
            corpus_version,
            prompt_version,
            route.kind,
            runtime_signature,
        )
        if active_runtime.state_store:
            cached = active_runtime.state_store.get_query_cache(cache_key)
            if cached:
                cached_response = QueryResponse.model_validate(cached)
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                cached_response.trace = cached_response.trace.model_copy(update={
                    'cache_hit': True,
                    'latency_ms': elapsed_ms,
                    'request_id': request_id,
                })
                log_event(
                    FORGE_LOGGER,
                    'query_cache_hit',
                    request_id=request_id,
                    route=route.kind,
                    route_reason=route.reason,
                )
                return cached_response
        if route.kind == 'aggregation':
            response = _aggregation_response(
                active_runtime,
                question,
                source,
                request_id=request_id,
                started=started,
            )
            if response is not None:
                _cache_query_response(
                    active_runtime,
                    cache_key,
                    corpus_version=corpus_version,
                    prompt_version=prompt_version,
                    response=response,
                )
                log_event(
                    FORGE_LOGGER,
                    'query_completed',
                    request_id=request_id,
                    route='aggregation',
                    route_reason=route.reason,
                    cache_hit=False,
                    candidates=0,
                    latency_ms=response.trace.latency_ms,
                )
                return response
            route = QueryRoute('rag', 'aggregation was not provably executable')
            cache_key = build_cache_key(
                question,
                document_id,
                corpus_version,
                prompt_version,
                route.kind,
                runtime_signature,
            )
        if document_id:
            execution = active_runtime.execute_query(question, document_id=document_id)
        else:
            execution = active_runtime.execute_query(payload.question)
        candidates = execution.candidates
        ranked = execution.ranked
        draft = execution.draft
    except (ProductionDependencyError, ProductionServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PRODUCTION_BACKEND_UNAVAILABLE", "message": str(exc)},
        ) from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    rerank_positions = {
        candidate.chunk.chunk_id: index
        for index, candidate in enumerate(ranked, start=1)
    }
    reranked_by_id = {candidate.chunk.chunk_id: candidate for candidate in ranked}
    selected_ids = {citation.chunk_id for citation in draft.citations}
    trace_candidates = [
        RetrievalCandidate(
            hybrid_rank=index,
            rerank_rank=rerank_positions.get(candidate.chunk.chunk_id),
            chunk_id=candidate.chunk.chunk_id,
            doc_id=candidate.chunk.doc_id,
            source_name=candidate.chunk.source_name,
            source_path=candidate.chunk.source_path,
            page=candidate.chunk.page,
            pages=candidate.chunk.pages,
            region=candidate.chunk.region,
            region_type=candidate.chunk.region_type,
            provenance=candidate.chunk.provenance,
            parent_id=candidate.chunk.parent_id,
            parent_title=candidate.chunk.parent_title,
            child_index=candidate.chunk.child_index,
            lexical_score=candidate.lexical_score,
            semantic_score=candidate.semantic_score,
            hybrid_score=candidate.hybrid_score,
            rerank_score=reranked_by_id.get(candidate.chunk.chunk_id, candidate).rerank_score,
            selected_for_answer=candidate.chunk.chunk_id in selected_ids,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    trace = RetrievalTrace(
        candidates_considered=len(candidates),
        reranked_count=len(ranked),
        reranker=active_runtime.reranker.name,
        evidence_threshold=active_runtime.answerer.evidence_threshold,
        latency_ms=elapsed_ms,
        retrieval_ms=execution.retrieval_ms,
        rerank_ms=execution.rerank_ms,
        generation_ms=execution.generation_ms,
        candidates=trace_candidates,
        route=route.kind,
        request_id=request_id,
        prompt_version=prompt_version,
    )
    response = QueryResponse(
        answer=draft.answer,
        abstained=draft.abstained,
        grounding=draft.grounding,
        citations=draft.citations,
        trace=trace,
        usage=draft.usage,
    )
    _cache_query_response(
        active_runtime,
        cache_key,
        corpus_version=corpus_version,
        prompt_version=prompt_version,
        response=response,
    )
    log_event(
        FORGE_LOGGER,
        'query_completed',
        request_id=request_id,
        route=route.kind,
        route_reason=route.reason,
        cache_hit=False,
        candidates=len(candidates),
        latency_ms=elapsed_ms,
    )
    return response


def require_admin(
    x_forge_admin_key: str | None = Header(default=None),
) -> None:
    expected = os.getenv('FORGE_ADMIN_API_KEY', '').strip()
    if not expected:
        return
    if x_forge_admin_key is None or not secrets.compare_digest(x_forge_admin_key, expected):
        raise HTTPException(
            status_code=401,
            detail={
                'code': 'ADMIN_KEY_REQUIRED',
                'message': 'A valid FORGE admin key is required.',
            },
        )


def _evaluation_configuration() -> dict:
    active_runtime = get_runtime()
    settings = getattr(active_runtime.retriever, 'settings', None)
    return {
        'reranker': active_runtime.reranker.name,
        'evidence_threshold': active_runtime.answerer.evidence_threshold,
        'models': {name: getattr(settings, name, None) for name in
                   ('dense_model', 'sparse_model', 'reranker_model', 'llm_model', 'retrieval_limit', 'rerank_limit')},
        'index': active_runtime.state_store.get_index_snapshot() if active_runtime.state_store else None,
        'scoring': 'source-page-v1 / lexical-proxy-v1',
    }


app.include_router(
    evaluation_router(
        get_evaluation_store,
        _execute_query,
        _evaluation_configuration,
        require_admin,
    )
)


def _upload_summary(
    *,
    document_id: str,
    filename: str,
    extension: str,
    source_path: str,
) -> dict[str, object]:
    return {
        "doc_id": document_id,
        "source_name": filename,
        "source_path": source_path,
        "format": extension.lstrip(".").upper(),
        "modality": extension.lstrip("."),
        "language": "multilingual",
        "factory_topic": "uploaded document",
        "status": "queued",
    }


def _public_job(
    job: dict[str, object],
    document: dict[str, object] | None = None,
    stages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    result = {
        "job_id": job["job_id"],
        "document_id": job["document_id"],
        "original_filename": job["original_filename"],
        "status": job["status"],
        "stage": job["stage"],
        "attempts": job["attempts"],
        "error": job["error"],
        "result": job["result"],
        "queued_at": job["queued_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "updated_at": job["updated_at"],
    }
    if document is not None:
        result["document"] = document
    if stages is not None:
        result["stages"] = stages
        result["progress"] = round(
            sum(int(stage.get('progress') or 0) for stage in stages) / len(stages)
        ) if stages else 0
    return result


def _public_document(document_id: str) -> dict[str, object] | None:
    active_runtime = get_runtime()
    documents = active_runtime.state_store.list_documents() if active_runtime.state_store is not None else []
    return next(
        (item for item in documents if item['doc_id'] == document_id),
        None,
    )


def _document_source_file(document: dict[str, object]) -> Path:
    raw_path = Path(str(document.get('source_path') or ''))
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail={
                'code': 'DOCUMENT_SOURCE_UNAVAILABLE',
                'message': 'The document source is outside the managed workspace.',
            },
        ) from exc
    if not resolved.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                'code': 'DOCUMENT_SOURCE_UNAVAILABLE',
                'message': 'The raw document file is no longer available.',
            },
        )
    return resolved


PREVIEW_MAX_ROWS = 200
PREVIEW_MAX_COLUMNS = 50


def _preview_table_html(rows: list[list[object]]) -> str:
    if not rows:
        return '<p class="forge-preview-empty">This source contains no tabular rows.</p>'
    bounded = [list(row[:PREVIEW_MAX_COLUMNS]) for row in rows[:PREVIEW_MAX_ROWS]]
    header = bounded[0]
    body = bounded[1:]
    head_html = ''.join(f'<th>{html.escape(str(value or ""))}</th>' for value in header)
    body_html = ''.join(
        '<tr>' + ''.join(
            f'<td>{html.escape(str(value if value is not None else ""))}</td>'
            for value in row[:len(header)]
        ) + '</tr>'
        for row in body
    )
    return (
        '<div class="forge-preview-table-wrap"><table class="forge-preview-table">'
        f'<thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody>'
        '</table></div>'
    )


def _render_document_preview(source: Path, filename: str) -> HTMLResponse:
    suffix = source.suffix.casefold()
    try:
        tables = read_table_sheets(source)
    except (OSError, UnicodeError, csv.Error, KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise HTTPException(status_code=422, detail={
            'code': 'DOCUMENT_PREVIEW_UNAVAILABLE',
            'message': 'The tabular document could not be rendered for browser preview.',
        }) from exc
    sections = ''.join(
        f'<section><h2>{html.escape(sheet_name)}</h2>{_preview_table_html(rows)}</section>'
        for sheet_name, rows in tables
    )
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(filename)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ color-scheme: light; font-family: Arial, sans-serif; }}
body {{ margin: 0; padding: 18px; color: #16364d; background: #ffffff; font-size: 13px; }}
h2 {{ margin: 0 0 10px; font-size: 14px; }}
section + section {{ margin-top: 24px; }}
.forge-preview-table-wrap {{ overflow: auto; border: 1px solid #d5e3e8; border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 560px; }}
th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5eef1; border-right: 1px solid #e5eef1; text-align: left; vertical-align: top; white-space: pre-wrap; }}
th {{ position: sticky; top: 0; color: #42657a; background: #eef5f7; font-size: 11px; }}
td {{ color: #23485e; background: #fff; }}
.forge-preview-empty {{ color: #6f8997; }}
</style></head><body>{sections}</body></html>'''
    return HTMLResponse(
        content=content,
        headers={
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'",
            'X-Content-Type-Options': 'nosniff',
        },
    )


@app.get('/api/documents/{document_id}/preview', response_class=HTMLResponse)
def preview_document(document_id: str) -> HTMLResponse:
    document = _public_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={
            'code': 'DOCUMENT_NOT_FOUND',
            'message': 'The document was not found.',
        })
    source = _document_source_file(document)
    if source.suffix.casefold() not in {'.csv', '.xlsx', '.xls'}:
        raise HTTPException(status_code=415, detail={
            'code': 'DOCUMENT_PREVIEW_NOT_REQUIRED',
            'message': 'This document type should be rendered using its native browser viewer.',
        })
    filename = Path(str(document.get('source_name') or source.name)).name
    return _render_document_preview(source, filename)

@app.get('/api/documents/{document_id}/raw')
def raw_document(document_id: str) -> FileResponse:
    document = _public_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={
                'code': 'DOCUMENT_NOT_FOUND',
                'message': 'The document was not found.',
            },
        )
    source = _document_source_file(document)
    filename = Path(str(document.get('source_name') or source.name)).name.replace('"', '')
    media_type = mimetypes.guess_type(source.name)[0] or 'application/octet-stream'
    return FileResponse(
        source,
        media_type=media_type,
        headers={'Content-Disposition': f'inline; filename="{filename}"'},
    )


@app.get("/api/ingestion/jobs/{job_id}")
def ingestion_job(job_id: str) -> dict[str, object]:
    active_runtime = get_runtime()
    if active_runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable ingestion is not enabled in this runtime.",
            },
        )
    job = active_runtime.state_store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "INGESTION_JOB_NOT_FOUND",
                "message": "The ingestion job was not found.",
            },
        )
    document = _public_document(str(job["document_id"]))
    stages = active_runtime.state_store.get_job_stages(job_id)
    return {"data": _public_job(job, document, stages)}


@app.get("/api/review-items")
def review_items(
    status: str | None = None,
    _authorized: None = Depends(require_admin),
) -> dict[str, object]:
    active_runtime = get_runtime()
    if active_runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable review state is not enabled in this runtime.",
            },
        )
    if status is not None and status not in {"pending", "accepted", "rejected"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_REVIEW_STATUS",
                "message": "Review status is invalid.",
            },
        )
    items = active_runtime.state_store.list_review_items(status)
    return {"data": items, "total": len(items)}


@app.patch("/api/review-items/{review_id}")
def update_review_item(
    review_id: str,
    decision: ReviewDecision,
    _authorized: None = Depends(require_admin),
) -> dict[str, object]:
    active_runtime = get_runtime()
    if active_runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable review state is not enabled in this runtime.",
            },
        )
    try:
        item = active_runtime.state_store.update_review_item(
            review_id,
            status=decision.status,
            notes=decision.notes,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "REVIEW_ITEM_NOT_FOUND",
                "message": "The review item was not found.",
            },
        ) from exc
    return {"data": item}


@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    _authorized: None = Depends(require_admin),
) -> dict[str, object]:
    active_runtime = get_runtime()
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_INPUT_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "Supported files are PDF, PNG, JPG, BMP, WEBP, XLS, XLSX, CSV, PPTX, and TXT.",
            },
        )

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": "Files must be 25 MB or smaller."},
        )

    if not _content_matches_extension(extension, data):
        raise HTTPException(
            status_code=422,
            detail={
                'code': 'INVALID_FILE_CONTENT',
                'message': 'The file content does not match its extension.',
            },
        )

    digest = hashlib.sha256(data).hexdigest()
    document_id = f"upload-{digest[:24]}"
    safe_filename = filename or f"{document_id}{extension}"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_ROOT / f"{document_id}{extension}"
    destination.write_bytes(data)

    if active_runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable ingestion is not enabled in this runtime.",
            },
        )

    source_path = destination.resolve()
    active_runtime.state_store.upsert_document(
        _upload_summary(
            document_id=document_id,
            filename=safe_filename,
            extension=extension,
            source_path=_relative_source_path(destination),
        ),
        content_hash=digest,
        size_bytes=len(data),
        status="queued",
    )
    job = active_runtime.state_store.enqueue_job(
        document_id=document_id,
        source_path=str(source_path),
        original_filename=safe_filename,
        content_hash=digest,
        idempotency_key=f"upload:{digest}:{extension}",
    )
    document = _public_document(document_id)
    response_status = 200 if job["status"] in {"indexed", "failed"} else 202
    return JSONResponse(
        status_code=response_status,
        content={
            "document_id": document_id,
            "filename": safe_filename,
            "status": job["status"],
            "message": "File queued for asynchronous ingestion.",
            "job_id": job["job_id"],
            "job": _public_job(job, document, active_runtime.state_store.get_job_stages(str(job["job_id"]))),
        },
    )
