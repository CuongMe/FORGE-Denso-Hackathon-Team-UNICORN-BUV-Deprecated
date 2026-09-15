from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.models import Chunk, RetrievedChunk


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "by",
    "for",
    "how",
    "is",
    "must",
    "of",
    "on",
    "the",
    "to",
    "was",
    "what",
    "when",
    "which",
    "who",
    "with",
    "in",
    "bao",
    "nhiêu",
    "phải",
    "trước",
    "khi",
    "xác",
    "nhận",
}

CONCEPT_ALIASES = {
    "target": {"target", "specification", "spec"},
    "pressure": {"pressure", "áp suất", "ap suat", "khí", "khi"},
    "air": {"air", "khí", "khi"},
    "zero": {"zero", "0", "bằng không", "bang khong"},
    "energy": {"energy", "năng lượng", "nang luong"},
    "team leader": {"team leader", "trưởng nhóm", "truong nhom"},
    "torque": {"torque", "tightening", "siết", "siet"},
    "defect": {"defect", "lỗi", "loi", "nonconformance"},
}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[\w]+", _fold(text), flags=re.UNICODE):
        if token in STOPWORDS or len(token) <= 1:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    return tokens


def _expanded_tokens(text: str) -> set[str]:
    normalized = _fold(text)
    expanded = _tokens(text)
    for concept, aliases in CONCEPT_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            expanded.update(_tokens(" ".join(aliases)))
        if concept in normalized:
            expanded.update(_tokens(" ".join(aliases)))
    return expanded


def _overlap(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    return len(query_tokens & content_tokens) / len(query_tokens)


def _structure_bonus(question: str, chunk: Chunk) -> float:
    """Prefer structured regions for lookup questions in the local fallback."""
    lookup_terms = {
        "date",
        "defect",
        "limit",
        "pressure",
        "quantity",
        "rate",
        "result",
        "specification",
        "target",
        "tolerance",
        "torque",
        "value",
    }
    question_tokens = _tokens(question)
    has_table = any(item.kind == "table" for item in chunk.provenance)
    if has_table and question_tokens & lookup_terms:
        return 0.08
    return 0.0


@dataclass(frozen=True)
class HybridRetriever:
    chunks: tuple[Chunk, ...] | None = None

    def __post_init__(self) -> None:
        if self.chunks is None:
            from app.corpus import load_source_pack_chunks

            object.__setattr__(self, "chunks", tuple(load_source_pack_chunks()))

    def search(self, question: str, limit: int = 8) -> list[RetrievedChunk]:
        query_tokens = _tokens(question)
        expanded_query = _expanded_tokens(question)
        scored: list[RetrievedChunk] = []

        for chunk in self.chunks or ():
            content_tokens = _tokens(chunk.content)
            expanded_content = _expanded_tokens(chunk.content)
            lexical = _overlap(query_tokens, content_tokens)
            semantic = _overlap(expanded_query, expanded_content)
            hybrid = round(
                min(1.0, (0.55 * lexical) + (0.45 * semantic) + _structure_bonus(question, chunk)),
                4,
            )
            if hybrid > 0:
                scored.append(
                    RetrievedChunk(
                        chunk=chunk,
                        lexical_score=round(lexical, 4),
                        semantic_score=round(semantic, 4),
                        hybrid_score=hybrid,
                    )
                )

        return sorted(scored, key=lambda item: item.hybrid_score, reverse=True)[:limit]


class CrossEncoderReranker:
    """Cross-encoder boundary with a deterministic fallback for the live demo."""

    name = "heuristic-demo-cross-encoder"

    def rerank(self, question: str, candidates: list[RetrievedChunk], limit: int = 5) -> list[RetrievedChunk]:
        query_tokens = _expanded_tokens(question)
        reranked: list[RetrievedChunk] = []
        for candidate in candidates:
            content_tokens = _expanded_tokens(
                candidate.chunk.content
            )
            overlap = _overlap(query_tokens, content_tokens)
            score = round((0.55 * candidate.hybrid_score) + (0.45 * overlap), 4)
            reranked.append(candidate.model_copy(update={"rerank_score": score}))
        return sorted(reranked, key=lambda item: item.rerank_score or 0, reverse=True)[:limit]
