from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from itertools import chain
from typing import Iterable, Mapping

from app.models import AggregationSummary


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
    def contains(term: str) -> bool:
        if term.isascii():
            return re.search(rf"\b{re.escape(term)}\b", lowered) is not None
        return term in lowered

    if any(contains(term) for term in ("average", "avg", "mean", "trung bình", "平均")):
        return "average"
    if any(contains(term) for term in ("maximum", "max", "highest", "最大")):
        return "max"
    if any(contains(term) for term in ("minimum", "min", "lowest", "最小")):
        return "min"
    if any(contains(term) for term in ("sum", "total", "tổng", "合計")):
        return "sum"
    if any(contains(term) for term in ("count", "how many", "number of", "bao nhiêu", "đếm", "何件")):
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


def _matching_filter(
    connection: sqlite3.Connection,
    question: str,
    columns: list[str],
    headers: set[str],
) -> str | None:
    query_tokens = _tokens(question)
    candidate: str | None = None
    for column in columns:
        for (value,) in connection.execute(f'SELECT DISTINCT "{column}" FROM aggregation_rows'):
            text = str(value or "").strip()
            value_tokens = _tokens(text)
            if len(text) >= 2 and text.casefold() not in headers and value_tokens and value_tokens <= query_tokens:
                if candidate is None or len(text) > len(candidate):
                    candidate = text
    return candidate


def aggregate_rows(
    question: str,
    rows: Iterable[Mapping[str, object]],
    *,
    source_doc_id: str,
    source_name: str,
) -> AggregationResult | None:
    """Run a deliberately small, auditable SQL aggregation over tabular rows."""
    operation = _operation(question)
    if not operation:
        return None

    iterator = iter(rows)
    first = next(iterator, None)
    if first is None:
        return None

    headers = [str(key) for key in first]
    columns = [f"v{index}" for index in range(len(headers))]
    numeric_columns = [f"n{index}" for index in range(len(headers))]
    definitions = ['"row_number" INTEGER NOT NULL']
    for column, numeric_column in zip(columns, numeric_columns):
        definitions.extend((f'"{column}" TEXT', f'"{numeric_column}"'))

    connection = sqlite3.connect(":memory:")
    connection.create_function(
        "CASEFOLD",
        1,
        lambda value: str(value or "").strip().casefold(),
        deterministic=True,
    )
    try:
        connection.execute(f"CREATE TABLE aggregation_rows ({', '.join(definitions)})")
        insert_columns = ['"row_number"'] + [
            name for pair in zip(columns, numeric_columns) for name in (f'"{pair[0]}"', f'"{pair[1]}"')
        ]
        placeholders = ", ".join("?" for _ in insert_columns)
        insert_sql = f"INSERT INTO aggregation_rows ({', '.join(insert_columns)}) VALUES ({placeholders})"
        for row_number, row in enumerate(chain((first,), iterator), start=1):
            values = [row.get(header, "") for header in headers]
            connection.execute(
                insert_sql,
                [row_number] + [
                    item
                    for value in values
                    for item in (str(value or ""), _number(value))
                ],
            )

        header_tokens = {header.casefold().strip() for header in headers}
        filter_text = _matching_filter(connection, question, columns, header_tokens)
        where = ""
        parameters: list[str] = []
        if filter_text:
            where = " WHERE " + " OR ".join(f"CASEFOLD(\"{column}\") = ?" for column in columns)
            parameters = [filter_text.casefold()] * len(columns)

        rows_considered = connection.execute("SELECT COUNT(*) FROM aggregation_rows").fetchone()[0]
        rows_matched = connection.execute(f"SELECT COUNT(*) FROM aggregation_rows{where}", parameters).fetchone()[0]
        column: str | None = None
        if operation == "count":
            value = rows_matched
        else:
            query_tokens = _tokens(question)
            selected_column = next((
                index for index, header in enumerate(headers)
                if _tokens(header) & query_tokens
                and connection.execute(
                    f'SELECT COUNT("{numeric_columns[index]}") FROM aggregation_rows{where}', parameters
                ).fetchone()[0]
            ), None)
            if selected_column is None:
                return None
            column = headers[selected_column]
            sql_operation = {"sum": "SUM", "average": "AVG", "min": "MIN", "max": "MAX"}[operation]
            value = connection.execute(
                f'SELECT {sql_operation}("{numeric_columns[selected_column]}") FROM aggregation_rows{where}',
                parameters,
            ).fetchone()[0]
            if value is None:
                return None
            if isinstance(value, float) and value.is_integer():
                value = int(value)

        summary = AggregationSummary(
            operation=operation,
            value=value,
            source_doc_id=source_doc_id,
            source_name=source_name,
            column=column,
            filter_text=filter_text,
            rows_considered=rows_considered,
            rows_matched=rows_matched,
        )
        qualifier = f" matching '{filter_text}'" if filter_text else ""
        if operation == "count":
            answer = f"{value} rows{qualifier} were found in {source_name}."
        elif operation == "average":
            answer = f"The average of {column}{qualifier} is {value} in {source_name}."
        else:
            answer = f"The {operation} of {column}{qualifier} is {value} in {source_name}."
        return AggregationResult(summary=summary, answer=answer)
    finally:
        connection.close()
