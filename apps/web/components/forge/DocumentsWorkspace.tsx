'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import documentPreviews from '@/data/document-previews.json';

import type { DocumentChunkPreview, DocumentSummary, HealthResponse } from '@/lib/types';

import { getDocumentChunks, getDocumentPreviewUrl, getDocumentRawUrl } from '@/lib/api';
import { ArrowRightIcon, FileIcon, SearchIcon } from './ForgeIcons';

export type DocumentFilter = 'ALL' | 'PDF' | 'PPTX' | 'TXT' | 'XLS' | 'XLSX' | 'CSV' | 'DXF' | 'IMAGE';

type DocumentsWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  filter?: DocumentFilter;
  onFilterChange?: (filter: DocumentFilter) => void;
  vercelDemo?: boolean;
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

function RailFilters({ documents, active, onChange }: { documents: DocumentSummary[]; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  const t = useTranslations();
  const filters: DocumentFilter[] = ['ALL', 'PDF', 'PPTX', 'TXT', 'XLS', 'XLSX', 'CSV', 'DXF', 'IMAGE'];
  return (
    <div className='forge-rail-filter-stack' aria-label={t('documents.filterLabel')}>
      {filters.map((filter) => {
        const count = filter === 'ALL' ? documents.length : documents.filter((document) => typeFor(document) === filter).length;
        return (
          <button key={filter} type='button' className={'forge-rail-filter ' + (active === filter ? 'is-active' : '')} onClick={() => onChange(filter)} aria-pressed={active === filter}>
            <span className={'forge-file-type-dot ' + filter.toLowerCase()}>{filter === 'ALL' ? <FileIcon /> : filter === 'IMAGE' ? 'IMG' : filter}</span>
            {filter === 'ALL' ? t('documents.allSources') : filter === 'IMAGE' ? t('rail.images') : filter}<small>{count}</small>
          </button>
        );
      })}
    </div>
  );
}

export function DocumentsRail({ documents, health, active, onChange }: { documents: DocumentSummary[]; health: HealthResponse | null; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  const t = useTranslations();
  return (
    <div className='forge-rail-content forge-document-rail'>
      <div className='forge-rail-heading'>
        <div><p className='forge-eyebrow'>DOCUMENT LIBRARY</p><p className='forge-rail-helper'>{health?.chunks_count ?? '—'} chunks · ready</p></div>
        <span className='forge-rail-count'>{health?.documents_count ?? documents.length}<small>{t('documents.sources')}</small></span>
      </div>
      <div className='forge-rail-stat-grid'><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? '—'}</strong><span>CHUNKS</span></div></div>
      <p className='forge-rail-subheading'>{t('documents.fileTypes')}</p>
      <RailFilters documents={documents} active={active} onChange={onChange} />
      <div className='forge-index-health forge-rail-index-status'>
        <p className='forge-eyebrow'>{t('documents.indexStatus')}</p>
      <div className='forge-rail-status-card'><span className='forge-source-dot' /><div><strong>{t('documents.indexFromApi')}</strong><small>{t('documents.readySources', { count: documents.filter((document) => document.status === 'ready').length })}<br />{t('documents.noSyncTime')}</small></div></div>
      </div>
      <div className='forge-rail-scroll-hint'>{t('documents.scrollFilters')}</div>
    </div>
  );
}

function Preview({ document }: { document: DocumentSummary | null }) {
  const t = useTranslations();
  if (!document) return <aside className='forge-document-preview'><p className='forge-eyebrow'>{t('documents.preview')}</p><p className='forge-empty-copy'>{t('documents.selectSource')}</p></aside>;
  const type = typeFor(document);
  return (
    <aside className='forge-document-side'>
      <section className='forge-document-preview'>
        <div className='forge-preview-heading'><div><p className='forge-eyebrow'>{t('documents.preview')}</p><p className='forge-side-helper'>{t('documents.previewHelper')}</p></div><span className='forge-side-pill'>{document.status.toUpperCase()}</span></div>
        <div className='forge-current-reference forge-document-selected'>
          <p className='forge-eyebrow'>{t('documents.selected')}</p>
          <strong>{document.doc_id}</strong>
          <span>{document.factory_topic || t('documents.factorySource')}</span>
          <span>{type} · {locationFor(document, t)} · {document.chunk_count} {t('documents.chunks')}</span>
          <span>SOURCE PATH · {document.source_path}</span>
          <span>{regionLabel(document, t)}</span>
        </div>
      </section>
      <section className='forge-document-preview forge-index-health'>
        <p className='forge-eyebrow'>{t('documents.indexingHealth')}</p>
        <p className='forge-trace-flow'>INGEST → PARSE → INDEX</p>
        <div className='forge-health-list'>
          <div><span className='forge-source-dot' />DOCUMENTS<strong>{document.status.toUpperCase()}</strong></div>
          <div><span className='forge-source-dot blue' />CHUNKS<strong>{document.chunk_count}</strong></div>
          <div><span className='forge-source-dot purple' />PROVENANCE<strong>{document.region_types.length ? 'RECORDED' : 'MISSING'}</strong></div>
        </div>
        <small className='forge-side-helper'>{t('documents.healthHelper')}</small>
      </section>
    </aside>
  );
}

export function DocumentsWorkspace({ documents, health, filter: controlledFilter, onFilterChange, vercelDemo = false }: DocumentsWorkspaceProps) {
  const t = useTranslations();
  const [internalFilter, setInternalFilter] = useState<DocumentFilter>('ALL');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.doc_id ?? null);
  const [demoDocument, setDemoDocument] = useState<DocumentSummary | null>(null);
  const [rawDocument, setRawDocument] = useState<DocumentSummary | null>(null);
  const [demoChunksResult, setDemoChunksResult] = useState<{ docId: string; chunks: DocumentChunkPreview[]; error: boolean } | null>(null);
  const filter = controlledFilter ?? internalFilter;
  const setFilter = (nextFilter: DocumentFilter) => { setInternalFilter(nextFilter); onFilterChange?.(nextFilter); };
  const filterScrollRef = useRef<HTMLDivElement>(null);
  const scrollFilters = (direction: -1 | 1) => {
    if (filterScrollRef.current) filterScrollRef.current.scrollBy({ left: direction * filterScrollRef.current.clientWidth * 0.8, behavior: 'smooth' });
  };
  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const searchable = (document.doc_id + ' ' + document.source_name + ' ' + document.factory_topic + ' ' + document.language).toLowerCase();
      return (filter === 'ALL' || typeFor(document) === filter) && (!query || searchable.includes(query));
    });
  }, [documents, filter, search]);
  const selected = documents.find((document) => document.doc_id === selectedId) ?? filteredDocuments[0] ?? null;
  const selectedDocId = selected?.doc_id ?? null;
  const shouldLoadChunks = Boolean(demoDocument);

  useEffect(() => {
    if (!shouldLoadChunks || !selectedDocId) return;
    let active = true;
    void getDocumentChunks(selectedDocId).then(({ chunks }) => {
      if (active) setDemoChunksResult({ docId: selectedDocId, chunks, error: false });
    }).catch(() => {
      if (active) setDemoChunksResult({ docId: selectedDocId, chunks: [], error: true });
    });
    return () => { active = false; };
  }, [selectedDocId, shouldLoadChunks]);

  return (
    <div className='forge-workspace documents-workspace'>
      <div className='forge-workspace-heading documents-heading'><div><p className='forge-eyebrow'>{t('documents.eyebrow')}</p><h1>{t('documents.title')}</h1><p className='forge-workspace-helper'>{t('documents.helper')}</p></div><div className='forge-corpus-summary'><strong>{health?.documents_count ?? documents.length}</strong><span>{t('documents.sources')}</span></div></div>
      <div className='forge-search-bar'><SearchIcon /><input aria-label={t('documents.searchLabel')} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('documents.search')} /><strong>{filteredDocuments.length} {t('documents.sources')}</strong></div>
      <div className='documents-filter-controls'>
        <button type='button' className='forge-filter-chip documents-filter-arrow' aria-label={t('documents.previousTypes')} aria-controls='document-type-filters' onClick={() => scrollFilters(-1)}><ArrowRightIcon className='is-previous' /></button>
        <div id='document-type-filters' ref={filterScrollRef} className='forge-filter-row documents-filter-row' role='group' aria-label={t('documents.filterLabel')}>
          {(['ALL', 'PDF', 'PPTX', 'TXT', 'XLS', 'XLSX', 'CSV', 'DXF', 'IMAGE'] as DocumentFilter[]).map((item) => {
            const count = item === 'ALL' ? documents.length : documents.filter((document) => typeFor(document) === item).length;
            return <button key={item} type='button' className={'forge-filter-chip ' + (filter === item ? 'is-active' : '')} onClick={() => setFilter(item)}>{item} {count}</button>;
          })}
        </div>
        <button type='button' className='forge-filter-chip documents-filter-arrow' aria-label={t('documents.nextTypes')} aria-controls='document-type-filters' onClick={() => scrollFilters(1)}><ArrowRightIcon /></button>
      </div>
      <div className='forge-document-layout'>
        <section className='forge-document-table-card' aria-label={t('documents.library')}>
          <div className='forge-table-heading'><span>Showing {Math.min(filteredDocuments.length, 5)} of {documents.length || 0} documents · scroll for more</span></div>
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
        <Preview document={selected} />
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
