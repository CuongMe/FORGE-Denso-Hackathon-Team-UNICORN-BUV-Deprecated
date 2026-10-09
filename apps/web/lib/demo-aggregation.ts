import { DatabaseSync } from "node:sqlite";

import tabularData from "@/data/demo-tabular.json";
import type { AggregationSummary } from "./types";

type DemoTable = {
  doc_id: string;
  source_name: string;
  source_path: string;
  columns: string[];
  rows: Record<string, string | number | null>[];
};

export type DemoAggregation = {
  answer: string;
  summary: AggregationSummary;
};

const tables = (tabularData as { tables: DemoTable[] }).tables;

function tokens(value: string) {
  return new Set((value.normalize("NFKC").toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [])
    .map((token) => token.length > 3 && token.endsWith("s") ? token.slice(0, -1) : token));
}

function operationFor(question: string): AggregationSummary["operation"] | null {
  const normalized = question.normalize("NFKC").toLocaleLowerCase();
  const words = tokens(normalized);
  if (["average", "avg", "mean"].some((word) => words.has(word)) || normalized.includes("trung bình") || normalized.includes("平均")) return "average";
  if (words.has("count") || (words.has("how") && words.has("many")) || (words.has("number") && words.has("of")) || normalized.includes("bao nhiêu") || normalized.includes("đếm") || normalized.includes("何件")) return "count";
  if (["sum", "total"].some((word) => words.has(word)) || normalized.includes("tổng") || normalized.includes("合計")) return "sum";
  if (["maximum", "max", "highest"].some((word) => words.has(word)) || normalized.includes("最大")) return "max";
  if (["minimum", "min", "lowest"].some((word) => words.has(word)) || normalized.includes("最小")) return "min";
  return null;
}

function numberValue(value: string | number | null) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const normalized = value.replaceAll(",", "").trim();
  if (!normalized || !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/iu.test(normalized)) return null;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

function selectTable(question: string, operation: AggregationSummary["operation"], rankedDocIds: string[]) {
  const queryTokens = tokens(question);
  const ranked = new Map(rankedDocIds.map((docId, index) => [docId, index]));
  const matches = tables.map((table) => {
    const columnTokens = new Set(table.columns.flatMap((column) => [...tokens(column)]));
    const fileTokens = tokens(table.source_name.replace(/\.[^.]+$/u, ""));
    const values = new Set(table.rows.flatMap((row) => Object.values(row).flatMap((value) => [...tokens(String(value ?? ""))])));
    const columnOverlap = [...columnTokens].filter((token) => queryTokens.has(token)).length;
    const fileOverlap = [...fileTokens].filter((token) => queryTokens.has(token)).length;
    const valueOverlap = [...values].filter((token) => queryTokens.has(token)).length;
    const rank = ranked.get(table.doc_id);
    const score = columnOverlap * 5 + fileOverlap * 3 + valueOverlap + (rank === undefined ? 0 : 1 / (rank + 1));
    const eligible = operation === "count"
      ? columnOverlap + fileOverlap + valueOverlap > 0 || rank !== undefined
      : columnOverlap > 0;
    return { table, score, eligible };
  }).filter((item) => item.eligible).sort((left, right) => right.score - left.score);
  if (!matches.length || (matches[1] && matches[0].score === matches[1].score)) return null;
  return matches[0].table;
}

function matchingFilter(question: string, table: DemoTable) {
  const queryTokens = tokens(question);
  const headers = new Set(table.columns.map((header) => header.trim().normalize("NFKC").toLocaleLowerCase()));
  let candidate: string | null = null;
  for (const row of table.rows) {
    for (const value of Object.values(row)) {
      const text = String(value ?? "").trim();
      const valueTokens = tokens(text);
      if (text.length >= 2 && !headers.has(text.normalize("NFKC").toLocaleLowerCase()) && valueTokens.size > 0 && [...valueTokens].every((token) => queryTokens.has(token))) {
        if (candidate === null || text.length > candidate.length) candidate = text;
      }
    }
  }
  return candidate;
}

export function aggregateDemoTable(question: string, rankedDocIds: string[] = []): DemoAggregation | null {
  const operation = operationFor(question);
  if (!operation) return null;
  const table = selectTable(question, operation, rankedDocIds);
  if (!table) return null;

  const db = new DatabaseSync(":memory:");
  try {
    const filterColumns = table.columns.map((_, index) => `f${index}`);
    const numericColumns = table.columns.map((_, index) => `n${index}`);
    const definitions = table.columns.flatMap((_, index) => [`"v${index}" TEXT`, `"f${index}" TEXT`, `"n${index}"`]);
    db.exec(`CREATE TABLE demo_rows (${definitions.join(", ")})`);
    const insert = db.prepare(`INSERT INTO demo_rows VALUES (${definitions.map(() => "?").join(", ")})`);
    for (const row of table.rows) {
      const values = table.columns.flatMap((column) => {
        const value = row[column] ?? "";
        return [String(value), String(value).trim().normalize("NFKC").toLocaleLowerCase(), numberValue(value)];
      });
      insert.run(...values);
    }

    const filterText = matchingFilter(question, table);
    const filter = filterText === null ? "" : ` WHERE ${filterColumns.map((column) => `"${column}" = ?`).join(" OR ")}`;
    const parameters = filterText === null ? [] : filterColumns.map(() => filterText.trim().normalize("NFKC").toLocaleLowerCase());
    const rowsConsidered = Number((db.prepare("SELECT COUNT(*) AS count FROM demo_rows").get() as { count: number }).count);
    const rowsMatched = Number((db.prepare(`SELECT COUNT(*) AS count FROM demo_rows${filter}`).get(...parameters) as { count: number }).count);
    let column: string | null = null;
    let value: number;

    if (operation === "count") {
      value = rowsMatched;
    } else {
      const queryTokens = tokens(question);
      let selectedIndex = -1;
      let bestColumnScore = 0;
      table.columns.forEach((header, index) => {
        const score = [...tokens(header)].filter((token) => queryTokens.has(token)).length;
        const hasNumbers = Number((db.prepare(`SELECT COUNT("${numericColumns[index]}") AS count FROM demo_rows${filter}`).get(...parameters) as { count: number }).count) > 0;
        if (hasNumbers && score > bestColumnScore) {
          selectedIndex = index;
          bestColumnScore = score;
        }
      });
      if (selectedIndex < 0) return null;
      column = table.columns[selectedIndex];
      const sqlOperation = { sum: "SUM", average: "AVG", min: "MIN", max: "MAX" }[operation];
      const result = (db.prepare(`SELECT ${sqlOperation}("${numericColumns[selectedIndex]}") AS value FROM demo_rows${filter}`).get(...parameters) as { value: number | null }).value;
      if (result === null) return null;
      value = result;
    }

    const summary: AggregationSummary = {
      operation,
      value,
      source_doc_id: table.doc_id,
      source_name: table.source_name,
      column,
      filter_text: filterText,
      rows_considered: rowsConsidered,
      rows_matched: rowsMatched,
    };
    const qualifier = filterText ? ` matching '${filterText}'` : "";
    const answer = operation === "count"
      ? `${value} rows${qualifier} were found in ${table.source_name}.`
      : operation === "average"
        ? `The average of ${column}${qualifier} is ${value} in ${table.source_name}.`
        : `The ${operation} of ${column}${qualifier} is ${value} in ${table.source_name}.`;
    return { answer, summary };
  } finally {
    db.close();
  }
}
