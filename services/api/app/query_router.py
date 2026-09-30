from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


RouteKind = Literal["rag", "aggregation", "visual"]

_AGGREGATION_TERMS = frozenset(
    {
        "count",
        "how many",
        "number of",
        "sum",
        "total",
        "average",
        "avg",
        "mean",
        "minimum",
        "maximum",
        "min",
        "max",
        "group by",
        "bao nhiêu",
        "đếm",
        "tổng",
        "trung bình",
        "何件",
        "合計",
        "平均",
        "最大",
        "最小",
    }
)
_TABULAR_TERMS = frozenset(
    {
        "csv",
        "xlsx",
        "excel",
        "dataset",
        "data set",
        "table",
        "row",
        "rows",
        "column",
        "columns",
        "record",
        "records",
        "machine",
        "production",
        "routine",
        "check",
        "measurement",
        "log",
        "データ",
        "表",
    }
)
_VISUAL_TERMS = frozenset(
    {
        "image",
        "images",
        "photo",
        "picture",
        "screenshot",
        "visual",
        "diagram",
        "chart",
        "defect",
        "ảnh",
        "hình",
        "画像",
        "図",
    }
)


@dataclass(frozen=True, slots=True)
class QueryRoute:
    kind: RouteKind
    reason: str


def _contains_term(question: str, terms: frozenset[str]) -> bool:
    lowered = " ".join(question.casefold().split())
    return any(term in lowered for term in terms)


def classify_query(
    question: str,
    *,
    tabular_available: bool = False,
    referenced_format: str | None = None,
) -> QueryRoute:
    """Choose a specialist path only when the question has clear signals."""
    normalized_format = (referenced_format or "").casefold()
    visual = _contains_term(question, _VISUAL_TERMS)
    aggregation = _contains_term(question, _AGGREGATION_TERMS)
    tabular = tabular_available or normalized_format in {"csv", "xlsx", "xls"}
    if aggregation and tabular and _contains_term(question, _TABULAR_TERMS):
        return QueryRoute("aggregation", "aggregation operator with tabular evidence")
    if visual:
        return QueryRoute("visual", "visual or inspection language detected")
    return QueryRoute("rag", "no specialist route matched")
