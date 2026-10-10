import { useTranslations } from 'next-intl';
import type { QueryResponse, RetrievalCandidate } from '@/lib/types';

function formatLatency(value: number) {
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

function formatLocation(candidate: RetrievalCandidate, missing: string) {
  if (candidate.page != null) return `p. ${candidate.page}`;
  if (candidate.pages.length > 0) return `pp. ${candidate.pages.join(', ')}`;
  return missing;
}

function chunkLabel(candidate: RetrievalCandidate) {
  const suffix = candidate.chunk_id.startsWith(`${candidate.doc_id}:`)
    ? candidate.chunk_id.slice(candidate.doc_id.length + 1)
    : candidate.chunk_id;
  return suffix.replace(/^chunk[-_:]?/i, '');
}

function candidateScore(candidate: RetrievalCandidate) {
  return Math.max(0, Math.min(1, candidate.rerank_score ?? candidate.hybrid_score));
}

export function RetrievalTrace({ response, onViewRaw }: { response: QueryResponse; onViewRaw: (candidate: RetrievalCandidate) => void }) {
  const t = useTranslations();
  const candidates = [...(response.trace.candidates ?? [])]
    .sort((left, right) => {
      if (left.rerank_rank != null && right.rerank_rank != null) return left.rerank_rank - right.rerank_rank;
      if (left.rerank_rank != null) return -1;
      if (right.rerank_rank != null) return 1;
      return left.hybrid_rank - right.hybrid_rank;
    })
    .slice(0, 3);
  const flow = response.trace.route === 'aggregation'
    ? t('trace.flowAggregation')
    : response.trace.retrieval_mode === 'bm25'
      ? t('trace.flowBm25')
      : t('ask.traceFlow');
  const resultLabel = response.trace.route === 'aggregation' ? t('trace.sql') : t('trace.gen');
  const resultTime = response.trace.route === 'aggregation' ? response.trace.latency_ms : response.trace.generation_ms;

  return (
    <section className='forge-side-card forge-trace-card' aria-labelledby='retrieval-trace-heading'>
      <header>
        <h2 className='forge-eyebrow' id='retrieval-trace-heading'>{t('ask.retrievalTrace')}</h2>
        <p className='forge-trace-flow'>{flow}</p>
      </header>
      {candidates.length ? (
        <ol className='forge-trace-list' aria-label={t('trace.candidates')}>
          {candidates.map((candidate) => {
            const score = candidateScore(candidate);
            const chunk = chunkLabel(candidate);
            return (
              <li
                key={candidate.chunk_id}
                className={`forge-trace-item${candidate.selected_for_answer ? ' is-selected' : ''}`}
                aria-label={`${candidate.doc_id} · ${chunk} · ${formatLocation(candidate, t('documents.provenanceMissing'))} · ${score.toFixed(2)}${candidate.selected_for_answer ? ` · ${t('trace.answer')}` : ''}`}
                title={candidate.source_name}
              >
                <div className='forge-trace-row'>
                  <button type='button' className='forge-trace-source-button' aria-label={t('documents.viewRaw', { name: candidate.source_name })} title={t('documents.viewRaw', { name: candidate.source_name })} onClick={() => onViewRaw(candidate)}>
                    <span className='forge-trace-identity'><strong>{candidate.doc_id}</strong><span>·</span><code>{chunk}</code></span>
                  </button>
                  <strong className='forge-trace-score'>{score.toFixed(2)}</strong>
                </div>
                <div className='forge-trace-meter' role='meter' aria-label={`${candidate.doc_id} ${chunk}`} aria-valuemin={0} aria-valuemax={1} aria-valuenow={score}>
                  <span style={{ width: `${score * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className='forge-trace-empty' role='status'>{t('trace.noCandidates')}</p>
      )}
      <footer className='forge-trace-footer'>
        <span><b>{t('trace.retrieved')}</b><strong>{response.trace.retrieval_ms == null ? '—' : formatLatency(response.trace.retrieval_ms)}</strong></span>
        <span><b>{t('trace.rerank')}</b><strong>{response.trace.reranked_count === 0 || response.trace.rerank_ms == null ? '—' : formatLatency(response.trace.rerank_ms)}</strong></span>
        <span><b>{resultLabel}</b><strong>{resultTime == null ? '—' : formatLatency(resultTime)}</strong></span>
      </footer>
    </section>
  );
}
