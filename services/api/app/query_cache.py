from __future__ import annotations

import hashlib
import json


def build_cache_key(
    question: str,
    document_id: str | None,
    corpus_version: str,
    prompt_version: str,
    route: str,
    runtime_signature: str = "",
) -> str:
    material = {
        "question": " ".join(question.split()).casefold(),
        "document_id": document_id or "",
        "corpus_version": corpus_version,
        "prompt_version": prompt_version,
        "route": route,
        "runtime_signature": runtime_signature,
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
