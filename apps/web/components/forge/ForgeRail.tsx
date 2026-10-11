'use client';

import { useMemo, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';

import type { DocumentSummary, HealthResponse } from '@/lib/types';

import { ArrowRightIcon, FileIcon, SearchIcon } from './ForgeIcons';

type SourceFilter = 'ALL' | 'PDF' | 'PPTX' | 'TXT' | 'SHEETS' | 'CSV' | 'IMAGE';

const sourceFilterOptions: Array<{ id: SourceFilter; label: string }> = [
  { id: 'ALL', label: 'ALL' },
  { id: 'PDF', label: 'PDF' },
  { id: 'PPTX', label: 'PPTX' },
  { id: 'TXT', label: 'TXT' },
  { id: 'SHEETS', label: 'SHEETS' },
  { id: 'CSV', label: 'CSV' },
  { id: 'IMAGE', label: 'IMAGES' },
];

type ForgeRailProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  eyebrow: string;
  helper: string;
  onReference: (docId: string) => void;
};

function sourceType(document: DocumentSummary): Exclude<SourceFilter, 'ALL'> {
  const format = document.format.toUpperCase();
  if (format === 'PDF') return 'PDF';
  if (format === 'PPTX') return 'PPTX';
  if (format === 'TXT') return 'TXT';
  if (format === 'CSV') return 'CSV';
  if (format === 'XLS' || format === 'XLSX') return 'SHEETS';
  return 'IMAGE';
}
export function ForgeRail({ documents, health, eyebrow, helper, onReference }: ForgeRailProps) {
  const t = useTranslations();
  const [filter, setFilter] = useState<SourceFilter>('ALL');
  const [search, setSearch] = useState('');
  const filterScrollRef = useRef<HTMLDivElement>(null);
  const scrollFilters = (direction: -1 | 1) => {
    const filters = filterScrollRef.current;
    filters?.scrollBy({ left: direction * filters.clientWidth * 0.8, behavior: 'smooth' });
  };
  const filteredDocuments = useMemo(
    () => {
      const term = search.trim().toLowerCase();
      return documents.filter((document) => {
        const matchesFilter = filter === 'ALL' || sourceType(document) === filter;
        const searchableText = [document.doc_id, document.source_name, document.format, document.factory_topic].join(' ').toLowerCase();
        return matchesFilter && (!term || searchableText.includes(term));
      });
    },
    [documents, filter, search],
  );

  return (
    <div className="forge-rail-content forge-ask-rail">
      <div className="forge-rail-heading">
        <div>
          <p className="forge-eyebrow">{eyebrow}</p>
          <p className="forge-rail-helper">{t('rail.sourceFilesReady', { count: health?.documents_count ?? documents.length })}</p>
        </div>
        <span className="forge-rail-count">
          {health?.chunks_count ?? '--'}
          <small>{t('rail.chunks')}</small>
        </span>
      </div>

      <div className="forge-rail-stat-grid">
        <div><strong>{health?.chunks_count ?? '--'}</strong><span>{t('rail.chunks')}</span></div>
        <div><strong>{health?.documents_count ?? documents.length}</strong><span>{t('rail.sourcesCount')}</span></div>
      </div>

      <div className="forge-rail-section forge-rail-sources">
        <div className="forge-rail-section-heading">
          <div>
            <p className="forge-eyebrow">{eyebrow}</p>
            <p className="forge-rail-helper">{helper}</p>
          </div>
          <FileIcon className="forge-rail-icon" />
        </div>

        <div className="forge-source-search">
          <SearchIcon />
          <label className="forge-sr-only" htmlFor="source-search">{t('rail.searchLabel')}</label>
          <input id="source-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('rail.search')} />
        </div>

        <div className="forge-source-filter-controls">
          <button type="button" className="forge-source-filter forge-source-filter-arrow" aria-label={t('rail.previousFilters')} aria-controls="ask-source-filters" onClick={() => scrollFilters(-1)}><ArrowRightIcon className="is-previous" /></button>
          <div id="ask-source-filters" ref={filterScrollRef} className="forge-source-filters" role="group" aria-label={t('rail.filterLabel')}>
          {sourceFilterOptions.map(({ id, label }) => {
            const count = id === 'ALL' ? documents.length : documents.filter((document) => sourceType(document) === id).length;
            return (
              <button
                key={id}
                type="button"
                className={'forge-source-filter ' + (filter === id ? 'is-active' : '')}
                aria-pressed={filter === id}
                onClick={() => setFilter(id)}
              >
                {label}<span>{count}</span>
              </button>
            );
          })}
          </div>
          <button type="button" className="forge-source-filter forge-source-filter-arrow" aria-label={t('rail.nextFilters')} aria-controls="ask-source-filters" onClick={() => scrollFilters(1)}><ArrowRightIcon /></button>
        </div>

        <div className="forge-source-list" aria-label="Indexed sources">
          {!documents.length && <p className="forge-empty-copy">{t('rail.loading')}</p>}
          {documents.length > 0 && !filteredDocuments.length && <p className="forge-empty-copy">{t('rail.noMatch')}</p>}
          {filteredDocuments.map((document) => (
            <button
              key={document.doc_id}
              type="button"
              className="forge-source-card"
              title={t('rail.reference', { id: document.doc_id })}
              onClick={() => onReference(document.doc_id)}
            >
              <span className="forge-source-dot" />
              <span className="forge-source-copy">
                <strong>{document.doc_id}</strong>
                <small>{document.format} / {document.factory_topic || t('documents.factorySource')}</small>
              </span>
              <span className="forge-source-format">{document.format.toUpperCase()}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="forge-rail-scroll-hint">{t('rail.clickReference')}</div>
    </div>
  );
}
