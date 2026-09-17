import type { IngestionJob, IngestionStage, IngestionStageStatus } from '@/lib/types';

const DEFAULT_STAGES: Array<{ stage: string; label: string }> = [
  { stage: 'queued', label: 'Queued' },
  { stage: 'uploading', label: 'Uploading' },
  { stage: 'parsing', label: 'Parsing' },
  { stage: 'ocr', label: 'OCR' },
  { stage: 'table_extraction', label: 'Table Extraction' },
  { stage: 'vlm_analysis', label: 'VLM Analysis' },
  { stage: 'chunking', label: 'Chunking' },
  { stage: 'embedding', label: 'Embedding' },
  { stage: 'indexing', label: 'Indexing' },
  { stage: 'graph_extraction', label: 'Graph Extraction' },
  { stage: 'completed', label: 'Completed' },
];

function fallbackStages(job: IngestionJob): IngestionStage[] {
  const activeIndex = DEFAULT_STAGES.findIndex(({ stage }) => stage === job.stage);
  return DEFAULT_STAGES.map(({ stage, label }, index) => {
    const status: IngestionStageStatus = job.status === 'failed' && index === activeIndex
      ? 'failed'
      : index < activeIndex
        ? 'completed'
        : index === activeIndex
          ? 'started'
          : 'pending';
    return {
      stage,
      label,
      status,
      progress: status === 'completed' ? 100 : status === 'started' ? 50 : 0,
      message: status === 'pending' ? 'Waiting to start.' : status === 'started' ? 'In progress.' : status === 'failed' ? (job.error ?? 'Stage failed.') : 'Completed.',
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
  const stages = job.stages?.length ? job.stages : fallbackStages(job);
  const progress = Math.min(100, Math.max(0, Math.round(job.progress ?? stages.reduce((total, stage) => total + stage.progress, 0) / stages.length)));
  const isActive = job.status === 'queued' || job.status === 'processing';

  return (
    <section className={'forge-ingestion-pipeline ' + (job.status === 'failed' ? 'is-failed' : '')} aria-label='Document ingestion progress' aria-live='polite' aria-busy={isActive}>
      <div className='forge-ingestion-header'>
        <div>
          <p className='forge-eyebrow'>INGESTION PIPELINE</p>
          <strong>{job.original_filename}</strong>
        </div>
        <span className='forge-ingestion-percent'>{progress}%</span>
      </div>
      <div className='forge-ingestion-progress' role='progressbar' aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} aria-label={'Ingestion ' + progress + '% complete'}>
        <span style={{ width: progress + '%' }} />
      </div>
      <div className='forge-ingestion-stage-list'>
        {stages.map((stage) => (
          <div className={'forge-ingestion-stage is-' + stage.status} key={stage.stage}>
            <span className='forge-ingestion-stage-icon'>{stageIcon(stage.status)}</span>
            <div className='forge-ingestion-stage-copy'>
              <strong>{stage.label}</strong>
              <span>{stage.message || 'Waiting to start.'}</span>
            </div>
            <span className='forge-ingestion-stage-progress'>{stage.status === 'completed' ? 'DONE' : stage.status === 'failed' ? 'FAILED' : stage.status === 'started' ? stage.progress + '%' : 'WAITING'}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
