from __future__ import annotations

import hashlib
import mimetypes
import os
import time
import io
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.corpus import PROJECT_ROOT
from app.ingestion import SUPPORTED_INPUT_EXTENSIONS
from app.models import GraphResponse, QueryRequest, QueryResponse, RetrievalCandidate, RetrievalTrace
from app.models import ReviewDecision
from app.persistence import LifecycleStore
from app.production import ProductionDependencyError, ProductionServiceError
from app.runtime import build_runtime
from app.worker import IngestionWorker


UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


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
    if extension == '.webp':
        return len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    if extension == '.xlsx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
            return '[Content_Types].xml' in names and any(name.startswith('xl/') for name in names)
        except (OSError, ValueError, zipfile.BadZipFile):
            return False
    if extension == '.csv':
        try:
            data.decode('utf-8-sig')
            return True
        except UnicodeDecodeError:
            return False
    return False

runtime = build_runtime()
ingestion_worker: IngestionWorker | None = None


@asynccontextmanager
async def lifespan(_app):
    global ingestion_worker
    if runtime.demo_mode or runtime.state_store is None:
        yield
        return
    ingestion_worker = IngestionWorker(runtime, runtime.state_store)
    ingestion_worker.start()
    try:
        yield
    finally:
        ingestion_worker.stop()
        ingestion_worker = None

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
    allow_headers=["Content-Type"],
)


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
    readiness = runtime.readiness()
    return {
        'ready': readiness['ready'],
        'readiness': readiness,
        "status": "ok",
        "demo_mode": runtime.demo_mode,
        "runtime_mode": runtime.mode,
        "documents_count": len(runtime.document_list()),
        "chunks_count": runtime.chunks_count,
        "reranker": runtime.reranker.name,
        "graph": runtime.graph_status(),
        "ingestion": runtime.ingestion(),
    }


@app.get("/api/documents")
def documents() -> dict[str, object]:
    items = runtime.document_list()
    return {"data": items, "total": len(items)}


@app.get('/api/graph', response_model=GraphResponse)
def graph(
    node_id: str | None = Query(default=None, max_length=240),
    search: str | None = Query(default=None, max_length=120),
    depth: int = Query(default=1, ge=0, le=3),
    limit: int = Query(default=100, ge=1, le=500),
) -> GraphResponse:
    if runtime.graph_store is None:
        raise HTTPException(
            status_code=503,
            detail={'code': 'GRAPH_BACKEND_UNAVAILABLE', 'message': 'The Kùzu graph backend is unavailable.'},
        )
    return GraphResponse.model_validate(
        runtime.graph_store.snapshot(
            seed_id=node_id,
            search=search,
            depth=depth,
            limit=limit,
        )
    )


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    started = time.perf_counter()
    try:
        execution = runtime.execute_query(payload.question)
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
        reranker=runtime.reranker.name,
        evidence_threshold=runtime.answerer.evidence_threshold,
        latency_ms=elapsed_ms,
        candidates=trace_candidates,
    )
    return QueryResponse(
        answer=draft.answer,
        abstained=draft.abstained,
        grounding=draft.grounding,
        citations=draft.citations,
        trace=trace,
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
    if runtime.state_store is None:
        return None
    return next(
        (
            item
            for item in runtime.state_store.list_documents()
            if item['doc_id'] == document_id
        ),
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
    if runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable ingestion is not enabled in this runtime.",
            },
        )
    job = runtime.state_store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "INGESTION_JOB_NOT_FOUND",
                "message": "The ingestion job was not found.",
            },
        )
    document = _public_document(str(job["document_id"]))
    stages = runtime.state_store.get_job_stages(job_id)
    return {"data": _public_job(job, document, stages)}


@app.get("/api/review-items")
def review_items(status: str | None = None) -> dict[str, object]:
    if runtime.state_store is None:
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
    items = runtime.state_store.list_review_items(status)
    return {"data": items, "total": len(items)}


@app.patch("/api/review-items/{review_id}")
def update_review_item(
    review_id: str,
    decision: ReviewDecision,
) -> dict[str, object]:
    if runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable review state is not enabled in this runtime.",
            },
        )
    try:
        item = runtime.state_store.update_review_item(
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
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_INPUT_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "Supported files are PDF, PNG, JPG, WEBP, XLSX, and CSV.",
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

    if runtime.demo_mode:
        return {
            "document_id": document_id,
            "filename": safe_filename,
            "status": "received",
            "message": "File received for ingestion.",
            "ingestion": runtime.ingestion(),
        }

    if runtime.state_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "LIFECYCLE_STORE_UNAVAILABLE",
                "message": "Durable ingestion is not enabled in this runtime.",
            },
        )

    source_path = destination.resolve()
    runtime.state_store.upsert_document(
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
    job = runtime.state_store.enqueue_job(
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
            "job": _public_job(job, document, runtime.state_store.get_job_stages(str(job["job_id"]))),
        },
    )
