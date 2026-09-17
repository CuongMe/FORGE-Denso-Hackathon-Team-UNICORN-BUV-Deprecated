import type { QueryResponse, RetrievalCandidate } from '@/lib/types';

function formatLatency(value: number) {
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

function formatScore(value: number | null) {
  return value == null ? '-' : `${Math.round(value * 100)}%`;
}

function formatLocation(candidate: RetrievalCandidate) {
  if (candidate.page != null) return `p. ${candidate.page}`;
  if (candidate.pages.length > 0) return `pp. ${candidate.pages.join(', ')}`;
  return 'location not recorded';
}

export function RetrievalTrace({ response }: { response: QueryResponse }) {
  const candidates = response.trace.candidates ?? [];
  const metrics = [
    ['Candidates', String(response.trace.candidates_considered)],
    ['Reranked', String(response.trace.reranked_count)],
    ['Threshold', response.trace.evidence_threshold.toFixed(2)],
    ['Latency', formatLatency(response.trace.latency_ms)],
  ];

  return (
    <section className='forge-side-card forge-trace-card' aria-labelledby='retrieval-trace-heading'>
      <div className='forge-side-card-heading'>
        <div>
          <p className='forge-eyebrow' id='retrieval-trace-heading'>RETRIEVAL TRACE</p>
          <p className='forge-trace-flow'>HYBRID -&gt; RERANK -&gt; ANSWER</p>
        </div>
      </div>
      <p className='forge-side-helper'>Ranked candidate detail from the server</p>
      <div className='forge-trace-metrics'>
        {metrics.map(([label, value]) => (
          <div key={label}><span>{label}</span><strong>{value}</strong></div>
        ))}
      </div>
      <div className='forge-trace-scroll'>
        <table className='forge-trace-table'>
          <thead>
            <tr><th>#</th><th>SOURCE / CHUNK</th><th>LOCATION</th><th>HYBRID</th><th>RERANK</th><th>ANSWER</th></tr>
          </thead>
          <tbody>
            {candidates.length ? candidates.map((candidate) => (
              <tr key={candidate.chunk_id} className={candidate.selected_for_answer ? 'is-selected' : undefined}>
                <td>{candidate.hybrid_rank}</td>
                <td><strong>{candidate.doc_id}</strong><small>{candidate.chunk_id}</small></td>
                <td>{formatLocation(candidate)}</td>
                <td>{formatScore(candidate.hybrid_score)}</td>
                <td>{formatScore(candidate.rerank_score)}</td>
                <td>{candidate.selected_for_answer ? 'Yes' : '-'}</td>
              </tr>
            )) : (
              <tr><td colSpan={6}>No retrieval candidates were returned.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className='forge-trace-foot'>
        {response.trace.candidates_considered} candidates - {response.trace.reranked_count} reranked - {formatLatency(response.trace.latency_ms)}
      </p>
    </section>
  );
}
