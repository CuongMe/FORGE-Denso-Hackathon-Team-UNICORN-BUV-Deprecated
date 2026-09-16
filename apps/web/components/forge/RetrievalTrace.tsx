import type { QueryResponse } from "@/lib/types";

function formatLatency(value: number) {
  return value < 1000 ? String(Math.round(value)) + " ms" : (value / 1000).toFixed(1) + " s";
}

function formatScore(value: number) {
  return String(Math.round(value * 100)) + "%";
}

export function RetrievalTrace({ response }: { response: QueryResponse }) {
  const metrics = [
    ["Candidates", String(response.trace.candidates_considered)],
    ["Reranked", String(response.trace.reranked_count)],
    ["Threshold", response.trace.evidence_threshold.toFixed(2)],
    ["Latency", formatLatency(response.trace.latency_ms)],
  ];

  return (
    <details className="forge-retrieval-trace">
      <summary>RETRIEVAL TRACE <span>HYBRID + {response.trace.reranker}</span></summary>
      <div className="forge-trace-panel">
        <p className="forge-trace-caption">Ranked cited evidence returned for this answer.</p>
        <div className="forge-trace-metrics">{metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        <table className="forge-trace-table"><thead><tr><th>Rank</th><th>Source</th><th>Region</th><th>Score</th></tr></thead><tbody>{response.citations.length ? response.citations.map((citation, index) => <tr key={citation.chunk_id}><td>{index + 1}</td><td>{citation.doc_id}</td><td>p.{citation.page ?? "—"} / {citation.region_type}</td><td>{formatScore(citation.score)}</td></tr>) : <tr><td colSpan={4}>No evidence passed the answer threshold.</td></tr>}</tbody></table>
      </div>
    </details>
  );
}
