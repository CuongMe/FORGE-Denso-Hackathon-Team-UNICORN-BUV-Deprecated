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
    <section className="forge-side-card forge-trace-card" aria-labelledby="retrieval-trace-heading">
      <div className="forge-side-card-heading"><div><p className="forge-eyebrow" id="retrieval-trace-heading">RETRIEVAL TRACE</p><p className="forge-trace-flow">HYBRID → RERANK → ANSWER</p></div></div>
      <p className="forge-side-helper">Ranked candidate detail</p>
      <div className="forge-trace-metrics">{metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="forge-trace-scroll"><table className="forge-trace-table"><thead><tr><th>#</th><th>SOURCE / CHUNK</th><th>HYBRID</th><th>RERANK</th></tr></thead><tbody>{response.citations.length ? response.citations.map((citation, index) => <tr key={citation.chunk_id}><td>{index + 1}</td><td><strong>{citation.doc_id}</strong><small>{citation.chunk_id}</small></td><td>{formatScore(citation.score)}</td><td>{formatScore(citation.score)}</td></tr>) : <tr><td colSpan={4}>No evidence passed the answer threshold.</td></tr>}</tbody></table></div>
      <p className="forge-trace-foot">{response.trace.candidates_considered} candidates · {response.trace.reranked_count} reranked · {formatLatency(response.trace.latency_ms)}</p>
    </section>
  );
}
