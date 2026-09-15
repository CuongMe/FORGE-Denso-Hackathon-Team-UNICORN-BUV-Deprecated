from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.corpus import PROJECT_ROOT
from app.ingestion import SUPPORTED_INPUT_EXTENSIONS
from app.models import QueryRequest, QueryResponse, RetrievalTrace
from app.production import ProductionDependencyError, ProductionServiceError
from app.runtime import build_runtime


UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

runtime = build_runtime()
retriever = runtime.retriever
reranker = runtime.reranker
answerer = runtime.answerer

app = FastAPI(
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
    allow_methods=["GET", "POST"],
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
    return {
        "status": "ok",
        "demo_mode": runtime.demo_mode,
        "runtime_mode": runtime.mode,
        "documents_count": len(runtime.document_list()),
        "chunks_count": runtime.chunks_count,
        "reranker": reranker.name,
        "ingestion": runtime.ingestion(),
    }


@app.get("/api/documents")
def documents() -> dict[str, object]:
    items = runtime.document_list()
    return {"data": items, "total": len(items)}


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    started = time.perf_counter()
    try:
        retrieval_limit = getattr(getattr(retriever, "settings", None), "retrieval_limit", 8)
        rerank_limit = getattr(getattr(reranker, "settings", None), "rerank_limit", 5)
        candidates = retriever.search(payload.question, limit=retrieval_limit)
        ranked = reranker.rerank(payload.question, candidates, limit=rerank_limit)
        draft = answerer.answer(payload.question, ranked)
    except (ProductionDependencyError, ProductionServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PRODUCTION_BACKEND_UNAVAILABLE", "message": str(exc)},
        ) from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    trace = RetrievalTrace(
        candidates_considered=len(candidates),
        reranked_count=len(ranked),
        reranker=reranker.name,
        evidence_threshold=answerer.evidence_threshold,
        latency_ms=elapsed_ms,
    )
    return QueryResponse(
        answer=draft.answer,
        abstained=draft.abstained,
        citations=draft.citations,
        trace=trace,
    )


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or ""
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_INPUT_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "Supported files are PDF, PNG, JPG, XLSX, and CSV.",
            },
        )

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": "Files must be 25 MB or smaller."},
        )

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    document_id = f"upload-{uuid4().hex}"
    destination = UPLOAD_ROOT / f"{document_id}{extension}"
    destination.write_bytes(data)
    if not runtime.demo_mode:
        try:
            ingestion = await run_in_threadpool(
                runtime.ingest,
                destination,
                document_id,
                Path(filename).name,
            )
        except (ProductionDependencyError, ProductionServiceError, RuntimeError) as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "INGESTION_FAILED", "message": str(exc)},
            ) from exc
        return {
            "document_id": document_id,
            "filename": Path(filename).name,
            "status": "indexed",
            "message": "File converted, chunked, embedded, and indexed.",
            "ingestion": ingestion,
        }
    return {
        "document_id": document_id,
        "filename": Path(filename).name,
        "status": "received",
        "message": "File received for ingestion.",
        "ingestion": runtime.ingestion(),
    }
