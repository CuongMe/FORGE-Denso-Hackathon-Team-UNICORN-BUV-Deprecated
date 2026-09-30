from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from app.models import AggregationSummary
from app.tabular import read_table_rows


@dataclass(frozen=True, slots=True)
class AggregationResult:
    summary: AggregationSummary
    answer: str


def _tokens(value: str) -> set[str]:
    result: set[str] = set()
    for token in re.findall(r"\w+", value.casefold(), flags=re.UNICODE):
        result.add(token[:-1] if token.endswith("s") and len(token) > 3 else token)
    return result


def _operation(question: str) -> str | None:
    lowered = question.casefold()
    if any(term in lowered for term in ("average", "avg", "mean", "trung bình", "平均")):
        return "average"
    if any(term in lowered for term in ("maximum", "max", "highest", "最大")):
        return "max"
    if any(term in lowered for term in ("minimum", "min", "lowest", "最小")):
        return "min"
    if any(term in lowered for term in ("sum", "total", "tổng", "合計")):
        return "sum"
    if any(term in lowered for term in ("count", "how many", "number of", "bao nhiêu", "đếm", "何件")):
        return "count"
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _matching_filter(question: str, rows: list[Mapping[str, object]], headers: set[str]) -> str | None:
    query_tokens = _tokens(question)
    candidates: list[str] = []
    for row in rows:
        for value in row.values():
            text = str(value or "").strip()
            if len(text) >= 2 and text.casefold() not in headers:
                value_tokens = _tokens(text)
                if value_tokens and value_tokens <= query_tokens:
                    candidates.append(text)
    return max(candidates, key=len, default=None)


def aggregate_rows(
    question: str,
    rows: Iterable[Mapping[str, object]],
    *,
    source_doc_id: str,
    source_name: str,
) -> AggregationResult | None:
    """Run a deliberately small, auditable aggregation over tabular rows."""
    operation = _operation(question)
    materialized = [dict(row) for row in rows]
    if not operation or not materialized:
        return None
    headers = {str(key).casefold().strip() for key in materialized[0]}
    filter_text = _matching_filter(question, materialized, headers)
    matched = materialized
    if filter_text:
        matched = [
            row for row in materialized
            if any(str(value or "").strip().casefold() == filter_text.casefold() for value in row.values())
        ]

    column: str | None = None
    values: list[float] = []
    if operation != "count":
        query_tokens = _tokens(question)
        for header in materialized[0]:
            if _tokens(str(header)) & query_tokens:
                numeric = [_number(row.get(header)) for row in matched]
                values = [value for value in numeric if value is not None]
                if values:
                    column = str(header)
                    break
        if not values:
            return None

    if operation == "count":
        value: int | float = len(matched)
    elif operation == "sum":
        value = sum(values)
    elif operation == "average":
        value = sum(values) / len(values)
    elif operation == "min":
        value = min(values)
    else:
        value = max(values)
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    summary = AggregationSummary(
        operation=operation,
        value=value,
        source_doc_id=source_doc_id,
        source_name=source_name,
        column=column,
        filter_text=filter_text,
        rows_considered=len(materialized),
        rows_matched=len(matched),
    )
    qualifier = f" matching '{filter_text}'" if filter_text else ""
    if operation == "count":
        answer = f"{value} rows{qualifier} were found in {source_name}."
    elif operation == "average":
        answer = f"The average of {column}{qualifier} is {value} in {source_name}."
    else:
        answer = f"The {operation} of {column}{qualifier} is {value} in {source_name}."
    return AggregationResult(summary=summary, answer=answer)
