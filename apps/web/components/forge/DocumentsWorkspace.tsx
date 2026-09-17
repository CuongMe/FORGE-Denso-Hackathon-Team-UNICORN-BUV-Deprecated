'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';

import type { DocumentSummary, HealthResponse } from '@/lib/types';

import { getDocumentRawUrl } from '@/lib/api';
import { FileIcon, SearchIcon } from './ForgeIcons';

export type DocumentFilter = 'ALL' | 'PDF' | 'XLSX' | 'CSV' | 'IMAGE';

type DocumentsWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  filter?: DocumentFilter;
  onFilterChange?: (filter: DocumentFilter) => void;
};

function typeFor(document: DocumentSummary): Exclude<DocumentFilter, 'ALL'> {
  const value = (document.format + ' ' + document.modality).toLowerCase();
  if (value.includes('image') || ['png', 'jpg', 'jpeg', 'webp'].some((type) => value.includes(type))) return 'IMAGE';
  if (value.includes('xlsx') || value.includes('excel')) return 'XLSX';
  if (value.includes('csv')) return 'CSV';
  return 'PDF';
}

function labelFor(document: DocumentSummary) {
  return typeFor(document) === 'IMAGE' ? 'IMG' : typeFor(document);
}

function locationFor(document: DocumentSummary) {
  const type = typeFor(document);
  if (type === 'PDF') return document.page_count ? document.page_count + ' pages' : 'pages not recorded';
  if (type === 'XLSX') return document.sheet_count ? document.sheet_count + ' sheets' : 'sheets not recorded';
  if (type === 'CSV') {
    const rows = document.row_count ? document.row_count + ' rows' : 'rows not recorded';
    const columns = document.column_count ? document.column_count + ' columns' : 'columns not recorded';
    return rows + ' · ' + columns;
  }
  return document.image_count ? document.image_count + ' images' : 'images not recorded';
}

function regionLabel(document: DocumentSummary) {
  return document.region_types.length ? document.region_types.join(' · ').toUpperCase() : 'PROVENANCE NOT RECORDED';
}

function RailFilters({ documents, active, onChange }: { documents: DocumentSummary[]; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  const filters: DocumentFilter[] = ['ALL', 'PDF', 'XLSX', 'CSV', 'IMAGE'];
  return (
    <div className='forge-rail-filter-stack' aria-label='Filter documents by type'>
      {filters.map((filter) => {
        const count = filter === 'ALL' ? documents.length : documents.filter((document) => typeFor(document) === filter).length;
        return (
          <button key={filter} type='button' className={'forge-rail-filter ' + (active === filter ? 'is-active' : '')} onClick={() => onChange(filter)}>
            <span className={'forge-file-type-dot ' + filter.toLowerCase()}>{filter === 'ALL' ? <FileIcon /> : filter === 'IMAGE' ? 'IMG' : filter}</span>
            {filter === 'ALL' ? 'All sources' : filter === 'IMAGE' ? 'Images' : filter}<small>{count}</small>
          </button>
        );
      })}
    </div>
  );
}

export function DocumentsRail({ documents, health, active, onChange }: { documents: DocumentSummary[]; health: HealthResponse | null; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  return (
    <div className='forge-rail-content forge-document-rail'>
      <div className='forge-rail-heading'>
        <div><p className='forge-eyebrow'>DOCUMENT LIBRARY</p><p className='forge-rail-helper'>{health?.chunks_count ?? '—'} chunks · ready</p></div>
        <span className='forge-rail-count'>{health?.documents_count ?? documents.length}<small>SOURCES</small></span>
      </div>
      <div className='forge-rail-stat-grid'><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? '—'}</strong><span>CHUNKS</span></div></div>
      <p className='forge-rail-subheading'>FILE TYPES</p>
      <RailFilters documents={documents} active={active} onChange={onChange} />
      <div className='forge-index-health forge-rail-index-status'>
        <p className='forge-eyebrow'>INDEX STATUS</p>
        <div className='forge-rail-status-card'><span className='forge-source-dot' /><div><strong>INDEX STATUS FROM API</strong><small>{documents.filter((document) => document.status === 'ready').length} ready sources<br />No fabricated sync time</small></div></div>
      </div>
      <div className='forge-rail-scroll-hint'>SCROLL TO BROWSE FILTERS</div>
    </div>
  );
}

function Preview({ document }: { document: DocumentSummary | null }) {
  if (!document) return <aside className='forge-document-preview'><p className='forge-eyebrow'>DOCUMENT PREVIEW</p><p className='forge-empty-copy'>Select a source to inspect its metadata.</p></aside>;
  const type = typeFor(document);
  return (
    <aside className='forge-document-side'>
      <section className='forge-document-preview'>
        <div className='forge-preview-heading'><div><p className='forge-eyebrow'>DOCUMENT PREVIEW</p><p className='forge-side-helper'>Selected from document library</p></div><span className='forge-side-pill'>{document.status.toUpperCase()}</span></div>
        <div className='forge-current-reference forge-document-selected'>
          <p className='forge-eyebrow'>SELECTED DOCUMENT</p>
          <strong>{document.doc_id}</strong>
          <span>{document.factory_topic || 'Factory operations source'}</span>
          <span>{type} · {locationFor(document)} · {document.chunk_count} CHUNKS</span>
          <span>SOURCE PATH · {document.source_path}</span>
          <span>{regionLabel(document)}</span>
        </div>
        <div className='forge-related-docs'>
          <p className='forge-eyebrow'>LINKED DOCUMENTS</p>
          <p className='forge-side-helper'>Only server-derived relationships are shown here.</p>
          <p className='forge-empty-copy'>Relationship edges will appear when the graph index is enabled.</p>
        </div>
      </section>
      <section className='forge-document-preview forge-index-health'>
        <p className='forge-eyebrow'>INDEXING HEALTH</p>
        <p className='forge-trace-flow'>INGEST → PARSE → INDEX</p>
        <div className='forge-health-list'>
          <div><span className='forge-source-dot' />DOCUMENTS<strong>{document.status.toUpperCase()}</strong></div>
          <div><span className='forge-source-dot blue' />CHUNKS<strong>{document.chunk_count}</strong></div>
          <div><span className='forge-source-dot purple' />PROVENANCE<strong>{document.region_types.length ? 'RECORDED' : 'MISSING'}</strong></div>
        </div>
        <small className='forge-side-helper'>Counts and locations are read from the source.</small>
      </section>
    </aside>
  );
}

function RawDocumentModal({ document, onClose }: { document: DocumentSummary; onClose: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const type = typeFor(document);
  const rawUrl = getDocumentRawUrl(document.doc_id);

  useEffect(() => {
    closeButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className='forge-raw-modal-backdrop' onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className='forge-raw-modal' role='dialog' aria-modal='true' aria-labelledby='raw-document-title'>
        <header className='forge-raw-modal-header'>
          <div><p className='forge-eyebrow'>RAW DOCUMENT</p><h2 id='raw-document-title'>{document.source_name}</h2><span>{type} · {document.doc_id}</span></div>
          <button ref={closeButton} type='button' className='forge-raw-modal-close' aria-label='Close raw document viewer' onClick={onClose}>CLOSE</button>
        </header>
        <div className={'forge-raw-modal-viewer is-' + type.toLowerCase()}>
          {type === 'IMAGE' ? <Image src={rawUrl} alt={document.source_name} fill unoptimized sizes='100vw' /> : <iframe src={rawUrl} title={'Raw view of ' + document.source_name} />}
        </div>
        <p className='forge-raw-modal-note'>{type === 'XLSX' ? 'Spreadsheet files are served in their original format; your browser may download them if it cannot render XLSX inline.' : 'Server-served original file. Press Escape or Close to return to the document library.'}</p>
      </section>
    </div>
  );
}

export function DocumentsWorkspace({ documents, health, filter: controlledFilter, onFilterChange }: DocumentsWorkspaceProps) {
  const [internalFilter, setInternalFilter] = useState<DocumentFilter>('ALL');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.doc_id ?? null);
  const [rawDocument, setRawDocument] = useState<DocumentSummary | null>(null);
  const filter = controlledFilter ?? internalFilter;
  const setFilter = (nextFilter: DocumentFilter) => { setInternalFilter(nextFilter); onFilterChange?.(nextFilter); };
  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const searchable = (document.doc_id + ' ' + document.source_name + ' ' + document.factory_topic + ' ' + document.language).toLowerCase();
      return (filter === 'ALL' || typeFor(document) === filter) && (!query || searchable.includes(query));
    });
  }, [documents, filter, search]);
  const selected = documents.find((document) => document.doc_id === selectedId) ?? filteredDocuments[0] ?? null;

  return (
    <div className='forge-workspace documents-workspace'>
      <div className='forge-workspace-heading documents-heading'><div><p className='forge-eyebrow'>DOCUMENTS</p><h1>Document library</h1><p className='forge-workspace-helper'>Browse indexed sources, provenance, and ingestion status.</p></div><div className='forge-corpus-summary'><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div></div>
      <div className='forge-search-bar'><SearchIcon /><input aria-label='Search documents' value={search} onChange={(event) => setSearch(event.target.value)} placeholder='Search indexed documents...' /><strong>{filteredDocuments.length} SOURCES</strong></div>
      <div className='forge-filter-row documents-filter-row' aria-label='Document type filters'>
        {(['ALL', 'PDF', 'XLSX', 'CSV', 'IMAGE'] as DocumentFilter[]).map((item) => {
          const count = item === 'ALL' ? documents.length : documents.filter((document) => typeFor(document) === item).length;
          return <button key={item} type='button' className={'forge-filter-chip ' + (filter === item ? 'is-active' : '')} onClick={() => setFilter(item)}>{item} {count}</button>;
        })}
      </div>
      <div className='forge-document-layout'>
        <section className='forge-document-table-card' aria-label='Indexed document table'>
          <div className='forge-table-heading'><span>Showing {Math.min(filteredDocuments.length, 5)} of {documents.length || 0} documents · scroll for more</span></div>
          <div className='forge-document-table-scroll'>
            <table className='forge-document-table'><thead><tr><th>SOURCE</th><th>TYPE</th><th>PAGES / SHEETS</th><th>CHUNKS</th><th>STATUS</th><th>RAW FILE</th></tr></thead>
              <tbody>
                {filteredDocuments.map((document) => {
                  const type = typeFor(document);
                  return <tr id={document.doc_id} className={'forge-document-row ' + (selected?.doc_id === document.doc_id ? 'is-selected' : '')} key={document.doc_id} onClick={() => setSelectedId(document.doc_id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelectedId(document.doc_id); }} tabIndex={0}>
                    <td className='forge-document-cell'><div className='forge-document-name'><span className={'forge-file-dot ' + type.toLowerCase()}>{labelFor(document)}</span><div><strong>{document.doc_id}</strong><small>{document.factory_topic || 'Factory operations source'}</small></div></div></td>
                    <td className='forge-document-cell'>{type}</td><td className='forge-document-cell'>{locationFor(document)}</td><td className='forge-document-cell'><strong>{document.chunk_count}</strong></td><td className='forge-document-cell'><span className='forge-document-status'>{document.status.toUpperCase()}</span></td><td className='forge-document-cell'><button type='button' className='forge-raw-link' aria-label={'View raw ' + document.source_name} onClick={(event) => { event.stopPropagation(); setRawDocument(document); }}>VIEW</button></td>
                  </tr>;
                })}
                {!filteredDocuments.length && <tr><td colSpan={6} className='forge-document-cell'>No sources match this filter.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
        <Preview document={selected} />
      </div>
      {rawDocument && <RawDocumentModal document={rawDocument} onClose={() => setRawDocument(null)} />}
    </div>
  );
}
