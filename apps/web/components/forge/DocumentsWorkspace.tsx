'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import documentPreviews from '@/data/document-previews.json';

import type { DocumentChunkPreview, DocumentSummary, HealthResponse, IngestionJob } from '@/lib/types';

import { getDocumentChunks, getDocumentPreviewUrl, getDocumentRawUrl } from '@/lib/api';
import { SearchIcon } from './ForgeIcons';

export type DocumentFilter = 'ALL' | 'PDF' | 'PPTX' | 'TXT' | 'XLS' | 'XLSX' | 'CSV' | 'DXF' | 'IMAGE';
const DOCUMENT_FILTERS: DocumentFilter[] = ['ALL', 'PDF', 'PPTX', 'TXT', 'XLS', 'XLSX', 'CSV', 'DXF', 'IMAGE'];

type DocumentsWorkspaceProps = {
  documents: DocumentSummary[];
  filter?: DocumentFilter;
  onFilterChange?: (filter: DocumentFilter) => void;
  vercelDemo?: boolean;
  ingestionJobs: IngestionJob[];
};

function typeFor(document: DocumentSummary): Exclude<DocumentFilter, 'ALL'> {
  const value = (document.format + ' ' + document.modality).toLowerCase();
  if (value.includes('image') || ['png', 'jpg', 'jpeg', 'bmp', 'webp'].some((type) => value.includes(type))) return 'IMAGE';
  if (document.format.toUpperCase() === 'PPTX') return 'PPTX';
  if (document.format.toUpperCase() === 'TXT') return 'TXT';
  if (document.format.toUpperCase() === 'DXF') return 'DXF';
  if (value.includes('xlsx') || value.includes('excel')) return 'XLSX';
  if (value.includes('xls')) return 'XLS';
  if (value.includes('csv')) return 'CSV';
  return 'PDF';
}

function labelFor(document: DocumentSummary) {
  return typeFor(document) === 'IMAGE' ? 'IMG' : typeFor(document);
}

function locationFor(document: DocumentSummary, t: (key: string, values?: Record<string, string | number>) => string) {
  const type = typeFor(document);
  if (type === 'PDF') return document.page_count ? t('documents.pages', { count: document.page_count }) : t('documents.pagesMissing');
  if (type === 'PPTX') return document.page_count ? t('documents.slides', { count: document.page_count }) : t('documents.slidesMissing');
  if (type === 'TXT') return t('documents.textDocument');
  if (type === 'DXF') return `CAD drawing · ${document.chunk_count} chunks`;
  if (type === 'XLSX' || type === 'XLS') return document.sheet_count ? t('documents.sheets', { count: document.sheet_count }) : t('documents.sheetsMissing');
  if (type === 'CSV') {
    const rows = document.row_count ? t('documents.rows', { count: document.row_count }) : t('documents.rowsMissing');
    const columns = document.column_count ? t('documents.columns', { count: document.column_count }) : t('documents.columnsMissing');
    return rows + ' · ' + columns;
  }
  return document.image_count ? t('documents.images', { count: document.image_count }) : t('documents.imagesMissing');
}

function regionLabel(document: DocumentSummary, t: (key: string) => string) {
  return document.region_types.length ? document.region_types.join(' · ').toUpperCase() : t('documents.provenanceMissing');
}

export function DocumentsRail({ documents, health, ingestionJobs }: { documents: DocumentSummary[]; health: HealthResponse | null; ingestionJobs: IngestionJob[] }) {
  const t = useTranslations();
  const activeJobs = ingestionJobs.filter((job) => job.status === 'queued' || job.status === 'processing').length;
  const failedJobs = ingestionJobs.filter((job) => job.status === 'failed').length;
  return (
    <div className='forge-rail-content forge-document-rail'>
      <div className='forge-rail-heading'>
        <div><p className='forge-eyebrow'>DOCUMENT LIBRARY</p><p className='forge-rail-helper'>{health?.chunks_count ?? '—'} chunks · ready</p></div>
        <span className='forge-rail-count'>{health?.documents_count ?? documents.length}<small>{t('documents.sources')}</small></span>
      </div>
      <div className='forge-rail-stat-grid'><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? '—'}</strong><span>CHUNKS</span></div></div>
      <p className='forge-rail-subheading'>{t('documents.ingestionProgress')}</p>
      <div className='forge-rail-ingestion-counts'>
        <div><strong>{documents.filter((document) => document.status === 'ready').length}</strong><span>{t('documents.ingestionReady')}</span></div>
        <div><strong>{activeJobs}</strong><span>{t('documents.ingestionActive')}</span></div>
        <div><strong>{failedJobs}</strong><span>{t('documents.ingestionFailed')}</span></div>
      </div>
    </div>
  );
}

function Preview({ document, ingestionJobs }: { document: DocumentSummary | null; ingestionJobs: IngestionJob[] }) {
  const t = useTranslations();
  const type = document ? typeFor(document) : null;
  return (
    <aside className='forge-document-side'>
      <section className='forge-document-preview'>
        <div className='forge-preview-heading'><div><p className='forge-eyebrow'>{t('documents.extractedText')}</p><p className='forge-side-helper'>{t('documents.extractedHelper')}</p></div><span className='forge-side-pill'>{document?.status.toUpperCase() ?? '—'}</span></div>
        {document ? <>
          <div className='forge-current-reference forge-document-selected'>
            <p className='forge-eyebrow'>{t('documents.selected')}</p>
            <strong>{document.doc_id}</strong>
            <span>{document.factory_topic || t('documents.factorySource')}</span>
            <span>{type} · {locationFor(document, t)} · {document.chunk_count} {t('documents.chunks')}</span>
            <span>SOURCE PATH · {document.source_path}</span>
            <span>{regionLabel(document, t)}</span>
          </div>
        </> : <p className='forge-empty-copy'>{t('documents.selectSource')}</p>}
      </section>
      <section className='forge-side-card forge-history-card' aria-labelledby='document-ingestion-heading'>
        <div className='forge-history-heading'><h2 id='document-ingestion-heading'>{t('documents.ingestionLog')}</h2></div>
        {ingestionJobs.length ? <ol className='forge-ingestion-log'>{ingestionJobs.slice(-8).reverse().map((job) => {
          const progress = Math.min(100, Math.max(0, Math.round(job.progress ?? 0)));
          const status = job.status === 'indexed' ? t('stage.completed') : job.status === 'failed' ? t('stage.failedLabel') : job.status === 'queued' ? t('stage.waitingLabel') : t('stage.' + job.stage);
          return <li key={job.job_id}><article className={'forge-rail-ingestion-job' + (job.status === 'failed' ? ' is-failed' : '')}>
            <div className='forge-rail-ingestion-job-heading'><strong title={job.original_filename}>{job.original_filename}</strong><span>{status}</span></div>
            <div className='forge-ingestion-progress' role='progressbar' aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} aria-label={t('ingestion.progress', { value: progress })}><span style={{ width: progress + '%' }} /></div>
            <small>{new Date(job.updated_at).toLocaleString()}</small>
            {job.error && <small>{job.error}</small>}
          </article></li>;
        })}</ol> : <p className='forge-history-empty'>{t('documents.noRecentUploads')}</p>}
      </section>
    </aside>
  );
}

export function DocumentsWorkspace({ documents, filter: controlledFilter, onFilterChange, vercelDemo = false, ingestionJobs }: DocumentsWorkspaceProps) {
  const t = useTranslations();
  const [internalFilter, setInternalFilter] = useState<DocumentFilter>('ALL');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.doc_id ?? null);
  const [demoDocument, setDemoDocument] = useState<DocumentSummary | null>(null);
  const [rawDocument, setRawDocument] = useState<DocumentSummary | null>(null);
  const [demoChunksResult, setDemoChunksResult] = useState<{ docId: string; chunks: DocumentChunkPreview[]; error: boolean } | null>(null);
  const filter = controlledFilter ?? internalFilter;
  const setFilter = (nextFilter: DocumentFilter) => { setInternalFilter(nextFilter); onFilterChange?.(nextFilter); };
  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const searchable = (document.doc_id + ' ' + document.source_name + ' ' + document.factory_topic + ' ' + document.language).toLowerCase();
      return (filter === 'ALL' || typeFor(document) === filter) && (!query || searchable.includes(query));
    });
  }, [documents, filter, search]);
  const selected = filteredDocuments.find((document) => document.doc_id === selectedId) ?? filteredDocuments[0] ?? null;
  const demoDocumentId = demoDocument?.doc_id ?? null;
  useEffect(() => {
    if (!demoDocumentId) return;
    let active = true;
    void getDocumentChunks(demoDocumentId).then(({ chunks }) => {
      if (active) setDemoChunksResult({ docId: demoDocumentId, chunks, error: false });
    }).catch(() => {
      if (active) setDemoChunksResult({ docId: demoDocumentId, chunks: [], error: true });
    });
    return () => { active = false; };
  }, [demoDocumentId]);

  return (
    <div className='forge-workspace documents-workspace'>
      <div className='forge-document-layout'>
        <main className='forge-document-main'>
          <div className='forge-workspace-heading documents-heading'><div><p className='forge-eyebrow'>{t('documents.eyebrow')}</p><h1>{t('documents.title')}</h1><p className='forge-workspace-helper'>{t('documents.helper')}</p></div></div>
          <div className='forge-search-bar'><SearchIcon /><input aria-label={t('documents.searchLabel')} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('documents.search')} /><strong>{filteredDocuments.length} {t('documents.sources')}</strong></div>
          <div className='forge-filter-row documents-filter-row' aria-label={t('documents.filterLabel')}>
            <span className='forge-filter-label'>{t('documents.filterByType')}</span>
            {DOCUMENT_FILTERS.map((item) => {
            const count = item === 'ALL' ? documents.length : documents.filter((document) => typeFor(document) === item).length;
            return <button key={item} type='button' className={'forge-filter-chip ' + (filter === item ? 'is-active' : '')} onClick={() => setFilter(item)}>{item} {count}</button>;
            })}
          </div>
        <section className='forge-document-table-card' aria-label={t('documents.library')}>
          <div className='forge-document-table-scroll'>
            <table className='forge-document-table'><thead><tr><th>{t('documents.source')}</th><th>{t('documents.type')}</th><th>{t('documents.pagesSheets')}</th><th>{t('documents.chunks')}</th><th>{t('documents.status')}</th><th>{t('documents.actions')}</th></tr></thead>
              <tbody>
                {filteredDocuments.map((document) => {
                  const type = typeFor(document);
                  return <tr id={'document-' + document.doc_id} className={'forge-document-row ' + (selected?.doc_id === document.doc_id ? 'is-selected' : '')} key={document.doc_id} onClick={() => setSelectedId(document.doc_id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelectedId(document.doc_id); }} tabIndex={0}>
                    <td className='forge-document-cell'><div className='forge-document-name'><span className={'forge-file-dot ' + type.toLowerCase()}>{labelFor(document)}</span><div><strong>{document.doc_id}</strong><small>{document.factory_topic || 'Factory operations source'}</small></div></div></td>
                    <td className='forge-document-cell'>{type}</td><td className='forge-document-cell'>{locationFor(document, t)}</td><td className='forge-document-cell'><strong>{document.chunk_count}</strong></td><td className='forge-document-cell'><span className='forge-document-status'>{document.status.toUpperCase()}</span></td><td className='forge-document-cell'><div className='forge-document-actions'>
                      <button type='button' className='forge-raw-link' aria-label={t('documents.viewExtracted', { name: document.source_name })} onClick={(event) => { event.stopPropagation(); setSelectedId(document.doc_id); setDemoDocument(document); }}>{t('documents.viewText')}</button>
                      <button type='button' className='forge-raw-link' aria-label={t('documents.viewRaw', { name: document.source_name })} onClick={(event) => { event.stopPropagation(); setSelectedId(document.doc_id); setRawDocument(document); }}>{t('documents.viewRawLabel')}</button>
                    </div></td>
                  </tr>;
                })}
                {!filteredDocuments.length && <tr><td colSpan={6} className='forge-document-cell'>{t('documents.noMatch')}</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
        </main>
        <Preview document={selected} ingestionJobs={ingestionJobs} />
      </div>
      {demoDocument && <DemoDocumentModal document={demoDocument} chunks={demoChunksResult?.docId === demoDocument.doc_id ? demoChunksResult.chunks : []} loading={demoChunksResult?.docId !== demoDocument.doc_id} error={demoChunksResult?.docId === demoDocument.doc_id && demoChunksResult.error} vercelDemo={vercelDemo} onClose={() => setDemoDocument(null)} />}
      {rawDocument && <RawDocumentModal document={rawDocument} vercelDemo={vercelDemo} onClose={() => setRawDocument(null)} />}
    </div>
  );
}

function RawDocumentModal({ document, vercelDemo, onClose }: { document: DocumentSummary; vercelDemo: boolean; onClose: () => void }) {
  const t = useTranslations();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  const type = typeFor(document);
  const isImage = type === 'IMAGE';
  const isSpreadsheet = type === 'CSV' || type === 'XLS' || type === 'XLSX';
  const sheets = documentPreviews[document.doc_id as keyof typeof documentPreviews] ?? [];
  const src = vercelDemo
    ? `/demo-documents/${encodeURIComponent(document.source_name)}`
    : isSpreadsheet ? getDocumentPreviewUrl(document.doc_id) : getDocumentRawUrl(document.doc_id);
  return <div className='forge-raw-modal-backdrop' onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className='forge-raw-modal' role='dialog' aria-modal='true' aria-labelledby='raw-document-title'>
      <header className='forge-raw-modal-header'><div><p className='forge-eyebrow'>{t('documents.rawDocument')}</p><h2 id='raw-document-title'>{document.source_name}</h2><span>{document.doc_id} · {document.factory_topic}</span></div><button ref={closeButton} type='button' className='forge-raw-modal-close' aria-label={t('documents.closeLabel')} onClick={onClose}>{t('documents.close')}</button></header>
      <div className={'forge-raw-modal-viewer' + (isImage ? ' is-image' : '') + (isSpreadsheet && vercelDemo ? ' forge-demo-document-content' : '')}>
        {isSpreadsheet && vercelDemo && sheets.length > 0 ? <SpreadsheetTables sheets={sheets} /> : isImage ? <Image src={src} alt={document.source_name} fill sizes='(max-width: 900px) 90vw, 850px' unoptimized /> : <iframe title={document.source_name} src={src} />}
      </div>
      <p className='forge-raw-modal-note'>{t('documents.originalFile')}</p>
    </section>
  </div>;
}

type PreviewSheet = (typeof documentPreviews)[keyof typeof documentPreviews][number];

export function SpreadsheetTables({ sheets }: { sheets: PreviewSheet[] }) {
  return <div className='forge-demo-sheets'>{sheets.map((sheet, index) => <details className='forge-demo-sheet' key={sheet.name} open={index === 0}><summary>{sheet.name}<span>{sheet.rows.length - 1} rows · {sheet.rows[0]?.length ?? 0} columns</span></summary><div className='forge-demo-table-scroll'><table className='forge-demo-preview-table'><thead><tr>{sheet.rows[0]?.map((heading, column) => <th key={`${column}-${heading}`}>{heading || `Column ${column + 1}`}</th>)}</tr></thead><tbody>{sheet.rows.slice(1).map((row, rowIndex) => <tr key={rowIndex}>{sheet.rows[0]?.map((_, column) => <td key={column}>{row[column] ?? '—'}</td>)}</tr>)}</tbody></table></div></details>)}</div>;
}

function DemoDocumentModal({ document, chunks, loading, error, vercelDemo, onClose }: { document: DocumentSummary; chunks: DocumentChunkPreview[]; loading: boolean; error: boolean; vercelDemo: boolean; onClose: () => void }) {
  const t = useTranslations();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  const type = typeFor(document);
  const sheets = documentPreviews[document.doc_id as keyof typeof documentPreviews] ?? [];
  return <div className='forge-raw-modal-backdrop' onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className='forge-raw-modal' role='dialog' aria-modal='true' aria-labelledby='demo-document-title'>
      <header className='forge-raw-modal-header'><div><p className='forge-eyebrow'>{type === 'IMAGE' ? 'IMAGE SOURCE · EXTRACTED TEXT' : type === 'XLS' || type === 'XLSX' || type === 'CSV' ? 'SPREADSHEET PREVIEW' : t('documents.extractedText')}</p><h2 id='demo-document-title'>{document.source_name}</h2><span>{document.doc_id} · {document.factory_topic}</span></div><button ref={closeButton} type='button' className='forge-raw-modal-close' aria-label={t('documents.closeLabel')} onClick={onClose}>{t('documents.close')}</button></header>
      <div className='forge-raw-modal-viewer forge-demo-document-content' aria-live='polite'>
        {type === 'IMAGE' && <div className='forge-demo-image-frame'><Image src={`/demo-documents/${encodeURIComponent(document.source_name)}`} alt={document.source_name} fill sizes='(max-width: 900px) 90vw, 850px' unoptimized /></div>}
        {type === 'XLS' && !vercelDemo && <iframe title={document.source_name} src={getDocumentPreviewUrl(document.doc_id)} sandbox='' style={{ width: '100%', minHeight: '65vh', border: 0, background: '#fff' }} />}
        {(type === 'XLS' || type === 'XLSX' || type === 'CSV') && sheets.length > 0 && <SpreadsheetTables sheets={sheets} />}
        {loading && <p role='status'>{t('documents.loadingExtracted')}</p>}
        {error && <p role='alert'>{t('documents.extractedUnavailable')}</p>}
        {!loading && !error && (type === 'XLS' || type === 'XLSX' || type === 'CSV') && sheets.length > 0 ? <details className='forge-demo-extracted'><summary>{t('documents.extractedText')} · {chunks.length} chunks</summary>{chunks.map((chunk) => <article className='forge-current-reference' key={chunk.chunk_id}><strong>{chunk.region || chunk.chunk_id}</strong><p>{chunk.content}</p></article>)}</details> : !loading && !error && chunks.map((chunk) => <article className='forge-current-reference' key={chunk.chunk_id}><strong>{chunk.region || chunk.chunk_id}</strong><span>{chunk.page == null ? chunk.region_type : `${t('ask.page', { value: chunk.page })} · ${chunk.region_type}`}</span><p>{chunk.content}</p></article>)}
      </div>
    </section>
  </div>;
}
