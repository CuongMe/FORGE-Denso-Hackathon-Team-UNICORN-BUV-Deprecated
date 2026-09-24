import { useTranslations } from 'next-intl';
import type { QueryResponse, RetrievalCandidate } from '@/lib/types';

function formatLatency(value: number) {
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

function formatScore(value: number | null) {
  return value == null ? '-' : `${Math.round(value * 100)}%`;
}

function formatRerankScore(value: number | null) {
  if (value == null) return '-';
  return value === 1 ? '100%' : value.toFixed(3);
}

function formatLocation(candidate: RetrievalCandidate, locationNotRecorded: string) {
  if (candidate.page != null) return `p. ${candidate.page}`;
  if (candidate.pages.length > 0) return `pp. ${candidate.pages.join(', ')}`;
  return locationNotRecorded;
}

export function RetrievalTrace({ response }: { response: QueryResponse }) {
  const t = useTranslations();
  const candidates = response.trace.candidates ?? [];
  const metrics = [
    [t('trace.candidates'), String(response.trace.candidates_considered)],
    [t('trace.reranked'), String(response.trace.reranked_count)],
    [t('trace.threshold'), response.trace.evidence_threshold.toFixed(2)],
    [t('trace.latency'), formatLatency(response.trace.latency_ms)],
  ];

  return (
    <section className='forge-side-card forge-trace-card' aria-labelledby='retrieval-trace-heading'>
      <div className='forge-side-card-heading'>
        <div>
          <p className='forge-eyebrow' id='retrieval-trace-heading'>{t('ask.retrievalTrace')}</p>
          <p className='forge-trace-flow'>{t('ask.traceFlow')}</p>
        </div>
      </div>
      <p className='forge-side-helper'>{t('trace.helper')}</p>
      <div className='forge-trace-metrics'>
        {metrics.map(([label, value]) => (
          <div key={label}><span>{label}</span><strong>{value}</strong></div>
        ))}
      </div>
      <div className='forge-trace-scroll'>
        <table className='forge-trace-table'>
          <thead>
            <tr><th>#</th><th>{t('trace.sourceChunk')}</th><th>{t('trace.location')}</th><th>{t('trace.hybrid')}</th><th>{t('trace.rerank')}</th><th>{t('trace.answer')}</th></tr>
          </thead>
          <tbody>
            {candidates.length ? candidates.map((candidate) => (
              <tr key={candidate.chunk_id} className={candidate.selected_for_answer ? 'is-selected' : undefined}>
                <td>{candidate.hybrid_rank}</td>
                <td><strong>{candidate.doc_id}</strong><small>{candidate.chunk_id}</small></td>
                <td>{formatLocation(candidate, t('documents.provenanceMissing'))}</td>
                <td>{formatScore(candidate.hybrid_score)}</td>
                <td>{formatRerankScore(candidate.rerank_score)}</td>
                <td>{candidate.selected_for_answer ? t('trace.yes') : '-'}</td>
              </tr>
            )) : (
              <tr><td colSpan={6}>{t('trace.noCandidates')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className='forge-trace-foot'>
        {t('trace.summary', { candidates: response.trace.candidates_considered, reranked: response.trace.reranked_count, latency: formatLatency(response.trace.latency_ms) })}
      </p>
    </section>
  );
}
