from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from app.ingestion import DoclingHybridChunkerAdapter
from app.models import Chunk
from app.production import chunks_from_docling


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACK_ROOT = PROJECT_ROOT / "data" / "denso_factory_hack_data_prep"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / ".forge-cache" / "source_pack_chunks_v2.json"
CACHE_SCHEMA_VERSION = 2


def _manifest() -> dict[str, dict[str, str]]:
    path = PACK_ROOT / "manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["doc_id"]: row for row in csv.DictReader(stream)}


def _source_signature(manifest: dict[str, dict[str, str]]) -> dict[str, str]:
    signature: dict[str, str] = {}
    for doc_id, row in manifest.items():
        relative_path = Path(row["relative_path"])
        source = (PACK_ROOT / relative_path).resolve()
        if PACK_ROOT.resolve() not in source.parents:
            raise ValueError(f"Manifest path escapes the source pack: {relative_path}")
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        signature[doc_id] = f"{relative_path.as_posix()}:{digest}"
    return signature


def _read_cached_chunks(
    cache_path: Path,
    *,
    signature: dict[str, str],
    adapter: DoclingHybridChunkerAdapter,
) -> list[Chunk] | None:
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") != CACHE_SCHEMA_VERSION
            or payload.get("cache_key") != adapter.cache_key
            or payload.get("source_signature") != signature
        ):
            return None
        return [Chunk.model_validate(item) for item in payload.get("chunks", [])]
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _write_cached_chunks(
    cache_path: Path,
    *,
    signature: dict[str, str],
    adapter: DoclingHybridChunkerAdapter,
    chunks: list[Chunk],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "cache_key": adapter.cache_key,
        "source_signature": signature,
        "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
    }
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(cache_path)


def load_source_pack_chunks(
    adapter: DoclingHybridChunkerAdapter | None = None,
    *,
    cache_path: Path | None = None,
) -> list[Chunk]:
    """Convert every manifest source file into real, provenance-aware chunks."""
    manifest = _manifest()
    converter = adapter or DoclingHybridChunkerAdapter()
    signature = _source_signature(manifest)
    selected_cache_path = cache_path or Path(
        os.getenv("FORGE_INGESTION_CACHE", str(DEFAULT_CACHE_PATH))
    )
    cache_enabled = os.getenv("FORGE_DISABLE_INGESTION_CACHE", "").casefold() not in {
        "1",
        "true",
        "yes",
    }
    if cache_enabled:
        cached = _read_cached_chunks(
            selected_cache_path,
            signature=signature,
            adapter=converter,
        )
        if cached is not None:
            return cached
    chunks: list[Chunk] = []

    for row in manifest.values():
        relative_path = Path(row["relative_path"])
        source = (PACK_ROOT / relative_path).resolve()
        if PACK_ROOT.resolve() not in source.parents:
            raise ValueError(f"Manifest path escapes the source pack: {relative_path}")
        try:
            records = converter.convert_and_chunk(source)
        except Exception as exc:
            raise RuntimeError(f"Failed to ingest source document {relative_path}.") from exc
        chunks.extend(
            chunks_from_docling(
                document_id=row["doc_id"],
                source_name=source.name,
                modality=row["modality"],
                records=records,
                source_path=(
                    Path("data") / PACK_ROOT.name / relative_path
                ).as_posix(),
                language=row["language"],
            )
        )

    if cache_enabled:
        _write_cached_chunks(
            selected_cache_path,
            signature=signature,
            adapter=converter,
            chunks=chunks,
        )
    return chunks

def list_demo_documents() -> list[dict[str, str]]:
    """Return the document collection shown in the demo UI."""
    manifest = _manifest()
    return [
        {
            "doc_id": row["doc_id"],
            "source_name": Path(row["relative_path"]).name,
            "format": row["format"],
            "modality": row["modality"],
            "language": row["language"],
            "factory_topic": row["factory_topic"],
        }
        for row in manifest.values()
    ]
