import { useTranslations } from 'next-intl';
import type { IngestionJob, IngestionStage, IngestionStageStatus } from '@/lib/types';

const DEFAULT_STAGES: Array<{ stage: string }> = [
  { stage: 'queued' },
  { stage: 'uploading' },
  { stage: 'parsing' },
  { stage: 'ocr' },
  { stage: 'table_extraction' },
  { stage: 'vlm_analysis' },
  { stage: 'chunking' },
  { stage: 'embedding' },
  { stage: 'indexing' },
  { stage: 'completed' },
];

function fallbackStages(job: IngestionJob, t: (key: string) => string): IngestionStage[] {
  const activeIndex = DEFAULT_STAGES.findIndex(({ stage }) => stage === job.stage);
  return DEFAULT_STAGES.map(({ stage }, index) => {
    const status: IngestionStageStatus = job.status === 'indexed'
      ? 'completed'
      : job.status === 'failed' && index === activeIndex
        ? 'failed'
        : index < activeIndex
        ? 'completed'
        : index === activeIndex
          ? 'started'
          : 'pending';
    return {
      stage,
      label: t('stage.' + stage),
      status,
      progress: status === 'completed' ? 100 : status === 'started' ? 50 : 0,
      message: status === 'pending' ? t('stage.waiting') : status === 'started' ? stage === 'uploading' ? t('stage.sending') : t('stage.progress') : status === 'failed' ? (job.error ?? t('stage.failed')) : t('stage.completedMessage'),
      error: status === 'failed' ? job.error : null,
      started_at: null,
      completed_at: null,
      updated_at: job.updated_at,
    };
  });
}

function stageIcon(status: IngestionStageStatus) {
  if (status === 'started') return <span className='forge-ingestion-spinner' aria-hidden='true' />;
  if (status === 'completed') return <span aria-hidden='true'>✓</span>;
  if (status === 'failed') return <span aria-hidden='true'>×</span>;
  return <span aria-hidden='true'>•</span>;
}

export function IngestionPipeline({ job }: { job: IngestionJob }) {
  const t = useTranslations();
  const stages = job.stages?.length ? job.stages : fallbackStages(job, t);
  const progress = Math.min(100, Math.max(0, Math.round(job.progress ?? stages.reduce((total, stage) => total + stage.progress, 0) / stages.length)));
  const isActive = job.status === 'queued' || job.status === 'processing';

  return (
    <section className={'forge-ingestion-pipeline ' + (job.status === 'failed' ? 'is-failed' : '')} aria-label={t('ingestion.aria')} aria-live='polite' aria-busy={isActive}>
      <div className='forge-ingestion-header'>
        <div>
          <p className='forge-eyebrow'>{t('ingestion.pipeline')}</p>
          <strong>{job.original_filename}</strong>
        </div>
        <span className='forge-ingestion-percent'>{progress}%</span>
      </div>
      <div className='forge-ingestion-progress' role='progressbar' aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} aria-label={t('ingestion.progress', { value: progress })}>
        <span style={{ width: progress + '%' }} />
      </div>
      {job.job_id.startsWith('demo-upload-') && <p className='forge-ingestion-demo-note' role='note'>{t('ingestion.demoNotice')}</p>}
      <div className='forge-ingestion-stage-list'>
        {stages.map((stage) => (
          <div className={'forge-ingestion-stage is-' + stage.status} key={stage.stage}>
            <span className='forge-ingestion-stage-icon'>{stageIcon(stage.status)}</span>
            <div className='forge-ingestion-stage-copy'>
              <strong>{t('stage.' + stage.stage)}</strong>
              <span>{stage.message || 'Waiting to start.'}</span>
            </div>
            <span className='forge-ingestion-stage-progress'>{stage.status === 'completed' ? t('stage.done') : stage.status === 'failed' ? t('stage.failedLabel') : stage.status === 'started' ? stage.stage === 'uploading' && stage.progress === 0 ? t('stage.waitingApi') : t('stage.percent', { value: stage.progress }) : t('stage.waitingLabel')}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
