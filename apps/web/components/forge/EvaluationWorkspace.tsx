'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useTranslations } from 'next-intl';
import { getEvaluation, getEvaluationDatasets, getEvaluations, getMetrics, setAdminKey, startEvaluation } from '@/lib/api';
import type { EvaluationDataset, EvaluationRun, HealthResponse, QueryMetrics } from '@/lib/types';
import { vercelDemoLimits } from '@/lib/vercel-demo-config';
import styles from './EvaluationWorkspace.module.css';

const datasetLabels = { all: 'eval.mixedBenchmark', golden: 'eval.goldenDataset', abstention: 'eval.abstentionHoldout' } as const;
const percent = (value: number | null | undefined) => value == null ? '—' : (value * 100).toFixed(1) + '%';
const duration = (value: number | null | undefined) => value == null ? '—' : (value / 1000).toFixed(2) + ' s';
const tokens = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat().format(value);
const cost = (value: number | null | undefined) => value == null ? '—' : '$' + value.toFixed(value < 0.01 ? 4 : 2);
const formatValue = (value: string) => value.replaceAll('_', ' ');
export function EvaluationRail({ vercelDemo = false }: { vercelDemo?: boolean }) {
  const t = useTranslations();
  return <div className='forge-rail-content'>
    <p className='forge-eyebrow'>{t('eval.qualityLab')}</p><h2>{t('eval.title')}</h2>
    <p className={styles.muted}>{vercelDemo ? t('eval.demoMetricsNote') : t('eval.helper')}</p>
    {!vercelDemo && <>
      <div className={styles.railNote}><strong>{t('eval.observe')}</strong><p>{t('eval.observeText')}</p></div>
      <div className={styles.railNote}><strong>{t('eval.evaluate')}</strong><p>{t('eval.evaluateText')}</p></div>
      <div className={styles.railNote}><strong>{t('eval.inspect')}</strong><p>{t('eval.inspectText')}</p></div>
      <p className={styles.note}>{t('eval.pendingNote')}</p>
    </>}
  </div>;
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <article className={styles.stat}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>;
}

export function EvaluationWorkspace({ mode, vercelDemo = false, health }: { mode: 'metrics' | 'evaluations'; vercelDemo?: boolean; health: HealthResponse | null }) {
  const t = useTranslations();
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [datasets, setDatasets] = useState<{ id: EvaluationDataset; count: number; answerable: number; signed_off: number; pending_review: number }[]>([]);
  const [dataset, setDataset] = useState<EvaluationDataset>('all');
  const [limit, setLimit] = useState(5);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!vercelDemo || mode === 'metrics');
  const [refresh, setRefresh] = useState(0);
  const [accessKey, setAccessKey] = useState('');

  useEffect(() => {
    if (vercelDemo) {
      if (mode !== 'metrics') return;
      let active = true;
      let inFlight = false;
      async function pollDemoMetrics() {
        if (inFlight) return;
        inFlight = true;
        try {
          const nextMetrics = await getMetrics();
          if (active) { setMetrics(nextMetrics); setError(null); }
        } catch (cause) {
          if (active) setError(cause instanceof Error ? cause.message : t('error.loadEval'));
        } finally {
          inFlight = false;
          if (active) setLoading(false);
        }
      }
      void pollDemoMetrics();
      const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void pollDemoMetrics(); }, 15_000);
      return () => { active = false; window.clearInterval(timer); };
    }
    let active = true;
    let inFlight = false;
    async function poll() {
      if (inFlight) return;
      inFlight = true;
      try {
        const [nextMetrics, nextRuns, nextDatasets] = await Promise.all([getMetrics(), getEvaluations(), getEvaluationDatasets()]);
        const id = selectedId ?? nextRuns.data[0]?.run_id;
        const detail = id ? await getEvaluation(id) : null;
        if (active) {
          setMetrics(nextMetrics); setRuns(nextRuns.data); setDatasets(nextDatasets.data); setRun(detail); setError(null);
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : t('error.loadEval'));
      } finally {
        inFlight = false;
        if (active) setLoading(false);
      }
    }
    void poll();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void poll(); }, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, [selectedId, refresh, t, vercelDemo, mode]);

  const available = datasets.find(item => item.id === dataset)?.count ?? 0;
  const running = runs.some(item => item.status === 'queued' || item.status === 'running') || run?.status === 'queued' || run?.status === 'running';
  const summary = run?.summary;

  async function launch() {
    setBusy(true); setError(null);
    try {
      const next = await startEvaluation(dataset, Math.min(limit, available));
      setRun(next); setSelectedId(next.run_id); setRefresh(value => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t('error.startEval'));
    } finally { setBusy(false); }
  }

  function download() {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = run.run_id + '.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function unlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminKey(accessKey);
    setError(null);
    setLoading(true);
    setRefresh(value => value + 1);
  }

  return <div className={styles.workspace}>
    <header className={styles.heading}><div><p className='forge-eyebrow'>{t('eval.qualityPerformance')}</p>
      <h1>{mode === 'metrics' ? t('eval.metricsTitle') : t('eval.evaluationTitle')}</h1>
      <p>{vercelDemo ? t('eval.demoHelper') : mode === 'metrics' ? t('eval.metricsHelper') : t('eval.evaluationHelper')}</p>
    </div><span className={styles.badge}>{vercelDemo ? t('eval.demoSnapshot') : running ? t('eval.inProgress') : t('eval.qualityLabBadge')}</span></header>

    {!vercelDemo && <details className={styles.access}><summary>{t('eval.protectedAccess')}</summary><form onSubmit={unlock}><label htmlFor='forge-admin-key'>{t('eval.adminKey')}</label><input id='forge-admin-key' type='password' autoComplete='off' value={accessKey} onChange={event => setAccessKey(event.target.value)} placeholder={t('eval.optionalDemo')} /><button type='submit'>{t('eval.applyKey')}</button></form><p>{t('eval.keyMemory')}</p></details>}

    {(!vercelDemo || mode === 'metrics') && error && <div className={styles.error} role='alert'>{error} <button onClick={() => setRefresh(value => value + 1)}>{t('eval.retry')}</button></div>}
    {(!vercelDemo || mode === 'metrics') && loading && <p role='status'>{t('eval.loading')}</p>}

    {vercelDemo && mode !== 'metrics' ? <>
      <div className={styles.stats}>
        <Stat label={t('eval.demoSources')} value={String(health?.documents_count ?? '—')} hint={t('eval.demoSourceHint')} />
        <Stat label={t('eval.demoChunks')} value={String(health?.chunks_count ?? '—')} hint={t('eval.demoChunkHint')} />
        <Stat label={t('eval.demoPerMinute')} value={String(vercelDemoLimits.perMinute)} hint={t('eval.demoMinuteHint')} />
        <Stat label={t('eval.demoDailyCap')} value={String(vercelDemoLimits.perDay)} hint={t('eval.demoDayHint')} />
      </div>
      <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.demoQualityTitle')}</h2></div><p className={styles.note}>{t('eval.demoMetricsNote')}</p></section>
    </> : mode === 'metrics' ? <>
      <div className={styles.stats}>
        <Stat label={t('eval.totalQueries')} value={metrics ? String(metrics.total_queries) : '—'} hint={t('eval.persistedAsk')} />
        <Stat label={t('eval.successRate')} value={percent(metrics?.success_rate)} hint={t('eval.completedNoErrors')} />
        <Stat label={t('eval.p50')} value={duration(metrics?.p50_latency_ms)} hint={t('eval.medianDuration')} />
        <Stat label={t('eval.p95')} value={duration(metrics?.p95_latency_ms)} hint={t('eval.failedDuration')} />
      </div>
      <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.responseSignals')}</h2><span>{t('eval.lastRequests', { count: metrics?.window_size ?? 0, days: metrics?.retention_days ?? '—' })}</span></div>
        <div className={styles.signals}>
          <div><span>{t('eval.citationCoverage')}</span><strong>{percent(metrics?.citation_rate)}</strong><p>{t('eval.citationCoverageText')}</p></div>
          <div><span>{t('eval.abstention')}</span><strong>{percent(metrics?.abstention_rate)}</strong><p>{t('eval.abstentionText')}</p></div>
          <div><span>{t('eval.geminiCost')}</span><strong>{tokens(metrics?.total_tokens)} · {cost(metrics?.estimated_cost_usd)}</strong><p>{t('eval.tokenText', { input: tokens(metrics?.prompt_tokens), output: tokens(metrics?.completion_tokens) })}</p></div>
        </div>
      </section>
      <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.recentRequests')}</h2><span>{t('eval.evaluationExcluded')}</span></div>
        {metrics?.recent.length ? <div className={styles.scroll}><table><thead><tr><th>{t('eval.time')}</th><th>{t('eval.result')}</th><th>{t('eval.duration')}</th><th>{t('eval.citations')}</th><th>{t('eval.tokens')}</th><th>{t('eval.estimatedCost')}</th></tr></thead><tbody>{metrics.recent.map(item => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.succeeded ? (item.abstained ? t('eval.noAnswer') : t('eval.answered')) : t('eval.failed')}</td><td>{duration(item.latency_ms)}</td><td>{item.citations}</td><td>{tokens(item.total_tokens)}</td><td>{cost(item.estimated_cost_usd)}</td></tr>)}</tbody></table></div> : <div className={styles.empty}><strong>{t('eval.firstQuery')}</strong><p>{t('eval.firstQueryText')}</p></div>}
      </section>
      {vercelDemo && <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.demoQualityTitle')}</h2></div><p className={styles.note}>{t('eval.demoMetricsNote')}</p></section>}
    </> : <>
      <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.runBenchmark')}</h2><span>{t('eval.availableCases', { count: datasets.find(item => item.id === 'all')?.count ?? '—' })}</span></div>
        <div className={styles.reviewStatus}><strong>{datasets.find(item => item.id === 'all')?.signed_off ?? 0} / {datasets.find(item => item.id === 'all')?.count ?? 38}</strong><span>{t('eval.humanSigned')}</span><small>{datasets.find(item => item.id === 'all')?.pending_review ?? 38} {t('eval.awaitingReview')}</small></div>
        <div className={styles.controls}>
          <label htmlFor='evaluation-dataset'><span>{t('eval.dataset')}</span><select id='evaluation-dataset' aria-label={t('eval.dataset')} value={dataset} onChange={event => { const next = event.target.value as EvaluationDataset; setDataset(next); setLimit(Math.min(limit, datasets.find(item => item.id === next)?.count ?? 5)); }}>{datasets.map(item => <option key={item.id} value={item.id}>{t(datasetLabels[item.id])} · {t('eval.cases', { count: item.count })}</option>)}</select></label>
          <label>{t('eval.caseLimit')}<input type='number' min={1} max={available || 38} value={limit} onChange={event => setLimit(Number(event.target.value))} /></label>
          <button className={styles.primary} disabled={busy || running || !available || !Number.isInteger(limit) || limit < 1 || limit > available} onClick={() => void launch()}>{busy ? t('eval.starting') : running ? t('eval.runProgress') : t('eval.runEvaluation')}</button>
        </div><p className={styles.note}>{t('eval.runNote')}</p>
      </section>

      <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.runHistory')}</h2><span>{t('eval.savedRuns', { count: runs.length })}</span></div>
        {runs.length > 0 ? <div className={styles.history}>{runs.map(item => <button key={item.run_id} className={item.run_id === run?.run_id ? styles.selected : ''} onClick={() => { setRun(null); setSelectedId(item.run_id); }} aria-pressed={item.run_id === run?.run_id}><strong>{t(datasetLabels[item.dataset])}</strong><span>{new Date(item.started_at ?? item.queued_at).toLocaleString()}</span><small>{t('status.' + item.status)} · {item.summary.completed + item.summary.failed}/{item.total}</small></button>)}</div> : <div className={styles.empty}><strong>{t('eval.baseline')}</strong><p>{t('eval.baselineText')}</p></div>}
      </section>

      {run && <>
        <div className={styles.runHeading}><div><h2>{t(datasetLabels[run.dataset])}</h2><p role='status'>{t('status.' + run.status)} · {summary!.completed} {t('eval.completed')} · {summary!.failed} {t('eval.failedCases')} / {t('eval.cases', { count: run.total })}</p></div><button onClick={download}>{t('eval.export')}</button></div>
        <progress className={styles.progress} aria-label={t('eval.progress')} value={summary!.completed + summary!.failed} max={run.total} />
        <div className={styles.stats}>
          <Stat label={t('eval.sourceRecall')} value={percent(summary?.source_recall)} hint={t('eval.sourceRecallHint')} />
          <Stat label={t('eval.answerability')} value={percent(summary?.answerability_correct)} hint={t('eval.answerabilityHint')} />
          <Stat label={t('eval.answerF1')} value={percent(summary?.answer_token_f1)} hint={t('eval.answerF1Hint')} />
          <Stat label={t('eval.p95')} value={duration(summary?.p95_latency_ms)} hint={t('eval.successfulCases')} />
        </div>
        <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.beforeAfter')}</h2><span>{t('eval.sameCutoff')}</span></div>
          <div className={styles.comparison}>{[[t('eval.hybridMrr'), summary?.hybrid_mrr], [t('eval.rerankedMrr'), summary?.reranked_mrr]].map(([label, value]) => <div key={String(label)}><span>{label}</span><meter min={0} max={1} value={typeof value === 'number' ? value : 0} aria-label={String(label)} /><strong>{typeof value === 'number' ? value.toFixed(3) : '—'}</strong></div>)}</div>
          <div className={styles.signals}><div><span>{t('eval.sourcePrecision')}</span><strong>{percent(summary?.source_precision)}</strong></div><div><span>{t('eval.citationPrecision')}</span><strong>{percent(summary?.citation_precision)}</strong></div><div><span>{t('eval.factCoverage')}</span><strong>{percent(summary?.required_fact_coverage)}</strong></div></div>
          <p className={styles.note}>{t('eval.scoreNote')}</p>
          <p className={styles.note}>{t('eval.mrrLift', { value: summary?.reranker_lift == null ? '—' : (summary.reranker_lift >= 0 ? '+' : '') + summary.reranker_lift.toFixed(3), score: percent(summary?.answerability_f1) })}</p>
        </section>
        <section className={styles.panel}><div className={styles.panelHeading}><h2>{t('eval.caseInspection')}</h2><span>{t('eval.expandCases')}</span></div>
          {run.results?.length ? run.results.map(item => <details key={item.case_id} className={styles.case}><summary><span className={styles.caseId}>{item.case_id}</span><span>{item.question}</span><span className={item.status === 'failed' || item.scores?.answerability_correct === false ? styles.warning : styles.good}>{item.status === 'failed' ? t('eval.error') : item.scores?.answerability_correct ? t('eval.decisionMatched') : t('eval.decisionMismatch')}</span></summary>
            <div className={styles.caseBody}><p className={styles.note}>{item.language} · {formatValue(item.question_type)} · {duration(item.latency_ms)} · {item.answerable ? t('eval.answerExpected') : t('eval.abstentionExpected')}</p>
              <div className={styles.answers}><div><h3>{t('eval.referenceAnswer')}</h3><p>{item.reference_answer}</p></div><div><h3>{t('eval.generatedAnswer')}</h3><p>{item.response?.answer ?? item.error}</p></div></div>
              <p className={styles.note}>{t('eval.recall')} {percent(item.scores?.source_recall)} · {t('eval.tokenF1')} {percent(item.scores?.answer_token_f1)} · {formatValue(item.verification_status)}</p>
              <h3>{t('eval.expectedEvidence')}</h3>
              {item.gold_evidence?.length ? item.gold_evidence.map((evidence, index) => <blockquote key={index}><strong>{evidence.doc_id} · {evidence.page == null ? t('eval.pageUnavailable') : t('eval.page', { value: evidence.page })} · {evidence.region}</strong><p>{evidence.quote}</p></blockquote>) : <p className={styles.note}>{t('eval.noEvidenceAbstention')}</p>}
              <h3>{t('eval.returnedCitations')}</h3>
              {item.response?.citations.map(citation => <blockquote key={citation.chunk_id}><strong>{citation.source_name} · {citation.page == null ? t('eval.pageUnavailable') : t('eval.page', { value: citation.page })}</strong><p>{citation.quote}</p></blockquote>)}
            </div></details>) : <p className={styles.note}>{t('eval.waitingCase')}</p>}
        </section>
        <details className={styles.panel}><summary>{t('eval.configuration')}</summary><pre className={styles.config}>{JSON.stringify({ dataset_hash: run.dataset_hash, ...run.configuration }, null, 2)}</pre></details>
      </>}
    </>}
  </div>;
}
