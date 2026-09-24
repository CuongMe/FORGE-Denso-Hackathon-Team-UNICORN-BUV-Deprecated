'use client';

import { useRef, type ChangeEvent, type FormEvent } from 'react';
import { useTranslations } from 'next-intl';

import type { DocumentSummary, HealthResponse, IngestionJob, QueryResponse } from '@/lib/types';

import { ArrowUpIcon, ImageIcon, UploadIcon } from './ForgeIcons';
import { ForgeCitationCard } from './ForgeCitationCard';
import { IngestionPipeline } from './IngestionPipeline';
import { PromptTable, type PromptItem } from './PromptTable';
import { RetrievalTrace } from './RetrievalTrace';

export type AskMessage = {
  id: string;
  role: 'user' | 'assistant' | 'upload';
  content: string;
  response?: QueryResponse;
  ingestionJob?: IngestionJob;
};

type AskWorkspaceProps = {
  health: HealthResponse | null;
  documents: DocumentSummary[];
  messages: AskMessage[];
  question: string;
  referencedDocument: DocumentSummary | null;
  isLoading: boolean;
  connectionError: string | null;
  uploadStatus: string | null;
  prompts: readonly PromptItem[];
  onQuestionChange: (value: string) => void;
  onSubmit: (question?: string) => void;
  onUpload: (file: File, kind: 'document' | 'image') => Promise<void>;
  onOpenDocument: (docId: string) => void;
  onClearReference: () => void;
};

function renderQuestion(content: string) {
  return content.split(/(@[A-Za-z0-9][A-Za-z0-9_-]*)/g).map((part, index) => part.startsWith('@')
    ? <span key={`${part}-${index}`} className="forge-message-reference">{part}</span>
    : <span key={`${part}-${index}`}>{part}</span>);
}

function RelatedSource({ docId, label, score }: { docId: string; label: string; score: string }) {
  return (
    <div className="forge-related-source">
      <span className="forge-related-dot" />
      <div><strong>{docId}</strong><small>{label}</small></div>
      <b>{score}</b>
    </div>
  );
}
function citationLocation(citation: QueryResponse['citations'][number] | null, format: string, t: (key: string, values?: Record<string, string | number>) => string) {
  if (citation?.page != null) return t('ask.page', { value: citation.page });
  if (citation?.pages.length) return t('ask.pages', { value: citation.pages.join(', ') });
  return format === 'CSV' || format === 'XLSX' ? t('ask.locationNotRecorded') : t('ask.pageNotRecorded');
}

function SourceDetails({ documents, response, onOpenDocument }: { documents: DocumentSummary[]; response: QueryResponse | null; onOpenDocument: (docId: string) => void }) {
  const t = useTranslations();
  const citation = response?.citations[0] ?? null;
  const current = documents.find((document) => document.doc_id === citation?.doc_id) ?? null;
  const relatedDocuments = response?.citations.slice(1, 3).map((item) => ({
    docId: item.doc_id,
    chunkId: item.chunk_id,
    label: item.region,
    score: Math.round(item.score * 100) + '%',
  })) ?? [];
  const format = current?.format?.toUpperCase() ?? citation?.source_name.split('.').pop()?.toUpperCase() ?? 'SOURCE';

  return (
    <section className="forge-side-card forge-source-details">
      <div className="forge-side-card-heading">
        <div>
          <p className="forge-eyebrow">{t('ask.sourceDetails')}</p>
          <p className="forge-side-helper">{t('ask.sourceDetailsHelper')}</p>
        </div>
        <span className="forge-side-pill">{t('ask.selectedChat')}</span>
      </div>
      {current && citation ? <div className="forge-current-reference">
        <p className="forge-eyebrow">{t('ask.currentReference')}</p>
        <strong>{current.doc_id}</strong>
        <span>{format} / {(current.factory_topic || t('ask.workInstruction')).toUpperCase()}</span>
        <span>{citationLocation(citation, format, t)} / {citation.region_type.toUpperCase()} / {citation.chunk_id}</span>
        <b>{citation.region}</b>
        <button type="button" className="forge-side-link" onClick={() => onOpenDocument(current.doc_id)}>OPEN REFERENCED DOCUMENT →</button>
      </div> : <div className="forge-current-reference is-empty">
        <p className="forge-eyebrow">{t('ask.currentReference')}</p>
        <strong>{t('ask.noSource')}</strong>
        <span>{t('ask.populateSource')}</span>
      </div>}
      <div className="forge-side-section">
        <p className="forge-eyebrow">{t('ask.related')}</p>
        <p className="forge-side-helper">{t('ask.relatedHelper')}</p>
        <div className="forge-related-list">
          {relatedDocuments.length ? relatedDocuments.map((item, index) => (
            <RelatedSource key={item.docId + ':' + item.chunkId + ':' + index} docId={item.docId} label={item.label} score={item.score} />
          )) : <p className="forge-empty-copy">{t('ask.noRelated')}</p>}
        </div>
      </div>
    </section>
  );
}

export function AskWorkspace({
  health,
  documents,
  messages,
  question,
  referencedDocument,
  isLoading,
  connectionError,
  uploadStatus,
  prompts,
  onQuestionChange,
  onSubmit,
  onUpload,
  onOpenDocument,
  onClearReference,
}: AskWorkspaceProps) {
  const t = useTranslations();
  const documentInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  let latestResponse: QueryResponse | null = null;
  messages.forEach((message) => {
    if (message.response) latestResponse = message.response;
  });
  const hasConversation = messages.some((message) => message.role === 'user' || message.role === 'upload');

  function handleFile(kind: 'document' | 'image', event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) void onUpload(file, kind);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className="forge-workspace ask-workspace">
      {connectionError && <div className="forge-connection-alert" role="alert">{t('ask.connection', { error: connectionError })}</div>}
      <div className="ask-layout">
        <div className="ask-primary">
          <section className={'forge-conversation forge-chatbox ' + (hasConversation ? 'has-conversation' : 'is-welcome')} aria-labelledby="ask-forge-heading" aria-live="polite" aria-busy={isLoading}>
            {!hasConversation && <div className="forge-workspace-heading forge-chatbox-heading">
              <div><p className="forge-eyebrow">{t('ask.ragBox')}</p><h1 id="ask-forge-heading">{t('ask.title')}</h1></div>
              <div className="forge-corpus-summary"><strong>{health?.chunks_count ?? '--'}</strong><span>{t('ask.corpus', { count: health?.documents_count ?? (documents.length || '--') })}</span></div>
            </div>}
            {!hasConversation && <PromptTable prompts={prompts} disabled={isLoading} onSelect={(value) => onSubmit(value)} />}
            {hasConversation && <div className="forge-conversation-heading"><span /><h2 id="conversation-heading">{t('ask.conversation')}</h2><span /></div>}
            <div className="forge-message-list">
              {messages.filter((message) => message.id !== 'welcome').map((message) => {
                if (message.role === 'upload') {
                  return (
                    <article key={message.id} className="forge-message forge-upload-message">
                      <div className="forge-message-meta"><span className="forge-avatar forge-upload-avatar">↑</span><span>{t('ask.docUpload')}</span></div>
                      <div className="forge-upload-card">
                        <p className="forge-upload-label">{t('ask.fileUpload')}</p>
                        <strong>{message.content}</strong>
                        {message.ingestionJob && <IngestionPipeline job={message.ingestionJob} />}
                      </div>
                    </article>
                  );
                }

                const isUser = message.role === 'user';
                const grounding = message.response?.grounding ?? (message.response?.abstained ? 'no_match' : 'grounded');
                const noMatch = grounding === 'no_match';
                const bestMatch = grounding === 'best_match';
                return (
                  <article key={message.id} className={'forge-message ' + (isUser ? 'is-user' : 'is-assistant')}>
                    <div className="forge-message-meta">
                      <span className="forge-avatar">{isUser ? 'Y' : 'F'}</span>
                      <span>{isUser ? t('ask.you') : t('ask.assistant')}</span>
                      {!isUser && message.response && <em className={noMatch || bestMatch ? 'is-warning' : 'is-grounded'}>{noMatch ? t('ask.noMatch') : bestMatch ? t('ask.bestMatch') : t('ask.grounded')}</em>}
                    </div>
                    <div className={'forge-message-card ' + (noMatch ? 'is-abstained' : '')}>
                      {isUser ? <p>{renderQuestion(message.content)}</p> : message.content ? <>
                        <p className="forge-answer-label">{t('ask.answer')}</p>
                        <p className="forge-answer-text">{message.content}</p>
                        {message.response && !noMatch && <div className="forge-answer-footer"><span>{bestMatch ? t('ask.closestEvidence') : t('ask.evidenceSupports')}</span><span>{message.response.trace.latency_ms < 1000 ? Math.round(message.response.trace.latency_ms) + ' ms' : (message.response.trace.latency_ms / 1000).toFixed(1) + ' s'}</span></div>}
                        {message.response && !noMatch && message.response.citations.length > 0 && <section className="forge-evidence-block" aria-label={t('ask.sourceEvidence')}>
                          <div className="forge-evidence-heading">
                            <div><strong>{t('ask.sourceEvidence')}</strong><span>{message.response.citations.length === 1 ? t('ask.citedSource', { count: message.response.citations.length }) : t('ask.citedSources', { count: message.response.citations.length })}</span></div>
                          </div>
                          <div className="forge-citation-list">{message.response.citations.map((citation) => <ForgeCitationCard key={citation.chunk_id} citation={citation} />)}</div>
                        </section>}
                        {noMatch && <p className="forge-abstention-note">{t('ask.noRetrieved')}</p>}
                      </> : <p className="forge-loading"><i /><i /><i /> {t('ask.ranking')}</p>}
                    </div>
                  </article>
                );
              })}
            </div>

            <footer className="forge-composer-wrap">
              {referencedDocument && <div className="forge-reference-chip" role="status">
                <span className="forge-reference-chip-mark">@</span>
                <span><strong>{referencedDocument.doc_id}</strong><small>{referencedDocument.source_name}</small></span>
                <button type="button" onClick={onClearReference} aria-label={t('ask.clearReference')} title={t('ask.clearReference')}>×</button>
              </div>}
              <form className="forge-composer" onSubmit={handleSubmit}>
                <div className="forge-composer-tools">
                  <button type="button" className="forge-icon-button" aria-label={t('ask.uploadDocument')} title={t('ask.uploadDocument')} onClick={() => documentInput.current?.click()} disabled={isLoading}><UploadIcon /></button>
                  <button type="button" className="forge-icon-button" aria-label={t('ask.uploadImage')} title={t('ask.uploadImage')} onClick={() => imageInput.current?.click()} disabled={isLoading}><ImageIcon /></button>
                  <input ref={documentInput} type="file" className="forge-hidden-input" accept=".pdf,.xlsx,.csv" onChange={(event) => handleFile('document', event)} />
                  <input ref={imageInput} type="file" className="forge-hidden-input" accept=".png,.jpg,.jpeg,.bmp,.webp" onChange={(event) => handleFile('image', event)} />
                </div>
                <label className="forge-sr-only" htmlFor="question-input">{t('ask.questionLabel')}</label>
                <textarea id="question-input" value={question} onChange={(event) => onQuestionChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSubmit(); } }} placeholder={t('ask.questionPlaceholder')} maxLength={500} disabled={isLoading} />
                <button type="submit" className="forge-send-button" aria-label={isLoading ? t('ask.working') : t('ask.ask')} disabled={isLoading || !question.trim()}><span>{isLoading ? t('ask.working') : t('ask.ask')}</span><ArrowUpIcon /></button>
              </form>
              <div className="forge-composer-footer"><span>Attach image · Click a source to reference it · Shift + Enter</span><span>{uploadStatus ?? question.length + '/500'}</span></div>
            </footer>
          </section>
        </div>

        <aside className="ask-side">
          <SourceDetails documents={documents} response={latestResponse} onOpenDocument={onOpenDocument} />
          {latestResponse ? <RetrievalTrace response={latestResponse} /> : <section className="forge-side-card forge-trace-card"><p className="forge-eyebrow">{t('ask.retrievalTrace')}</p><p className="forge-trace-flow">{t('ask.traceFlow')}</p><p className="forge-side-helper">{t('ask.traceHelper')}</p></section>}
        </aside>
      </div>
    </div>
  );
}
