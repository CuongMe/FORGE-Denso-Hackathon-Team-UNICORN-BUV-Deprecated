'use client';

import { useRef, type ChangeEvent, type FormEvent } from 'react';
import { useTranslations } from 'next-intl';

import type { DocumentSummary, HealthResponse, IngestionJob, QueryResponse } from '@/lib/types';
import { demoAnswers } from '@/lib/demo-answers';

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
  onReferenceDocument: (docId: string) => void;
  onClearReference: () => void;
  onClearChat: () => void;
  vercelDemo?: boolean;
};

function renderQuestion(content: string) {
  return content.split(/(@[A-Za-z0-9][A-Za-z0-9_-]*)/g).map((part, index) => part.startsWith('@')
    ? <span key={`${part}-${index}`} className="forge-message-reference">{part}</span>
    : <span key={`${part}-${index}`}>{part}</span>);
}

function SourceDetails({ documents, response, referencedDocument, onReferenceDocument }: { documents: DocumentSummary[]; response: QueryResponse | null; referencedDocument: DocumentSummary | null; onReferenceDocument: (docId: string) => void }) {
  const t = useTranslations();
  const citation = response?.citations[0] ?? null;
  const current = referencedDocument ?? documents.find((document) => document.doc_id === citation?.doc_id) ?? null;
  const format = current?.format?.toUpperCase() ?? citation?.source_name.split(".").pop()?.toUpperCase() ?? "SOURCE";
  const referenceId = current?.doc_id ?? citation?.doc_id;
  const relatedDocuments = [...new Set(response?.citations.slice(1).map((item) => item.doc_id) ?? [])].filter((docId) => docId !== referenceId).slice(0, 2);
  const location = current?.page_count
    ? t(format === "PPTX" ? "documents.slides" : "documents.pages", { count: current.page_count })
    : current?.sheet_count && ["XLS", "XLSX"].includes(format)
      ? t("documents.sheets", { count: current.sheet_count })
      : "";

  return (
    <section className="forge-side-card forge-source-details">
      <div className="forge-pinned-reference">
        <p className="forge-eyebrow">{t("ask.currentReference")}</p>
        <strong>{referenceId ? "@" + referenceId : t("ask.noSource")}</strong>
        <p>{current ? [current.factory_topic, format, location].filter(Boolean).join(" \u00b7 ") : citation?.source_name ?? t("ask.populateSource")}</p>
        {referenceId && <button type="button" className="forge-ask-about-document" onClick={() => onReferenceDocument(referenceId)}>{t("ask.askAboutDocument")}</button>}
      </div>
      <div className="forge-nearby-references">
        <p className="forge-eyebrow">{t("ask.related")}</p>
        {relatedDocuments.length ? relatedDocuments.map((docId) => <button key={docId} type="button" className="forge-nearby-source" onClick={() => onReferenceDocument(docId)}>@{docId}</button>) : <p className="forge-empty-copy">{t("ask.noRelated")}</p>}
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
  onReferenceDocument,
  onClearReference,
  onClearChat,
  vercelDemo = false,
}: AskWorkspaceProps) {
  const t = useTranslations();
  const documentInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  let latestResponse: QueryResponse | null = null;
  messages.forEach((message) => {
    if (message.response) latestResponse = message.response;
  });
  const hasConversation = messages.some((message) => message.role === 'user' || message.role === 'upload');
  const hasPendingUpload = messages.some((message) => message.role === 'upload' && ['queued', 'processing'].includes(message.ingestionJob?.status ?? ''));

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
            {hasConversation && <div className="forge-conversation-toolbar"><h2 id="conversation-heading">{t('ask.conversation')}</h2><button type="button" className="forge-clear-chat-button" onClick={onClearChat} disabled={isLoading || hasPendingUpload}>{t('ask.clearChat')}</button></div>}
            <div className="forge-message-list">
              {vercelDemo && !hasConversation && <article className='forge-message is-assistant'>
                <div className='forge-message-meta'><span className='forge-avatar'>F</span><span>{t('ask.assistant')}</span><em className='is-grounded'>{t('ask.sampleLabel')}</em></div>
                <div className='forge-message-card'>
                  <p className='forge-answer-label'>{t('ask.sampleQuestion')}</p>
                  <p className='forge-answer-text'>{t('ask.sampleAnswer')}</p>
                  <section className='forge-evidence-block' aria-label={t('ask.sourceEvidence')}><div className='forge-evidence-heading'><strong>{t('ask.sourceEvidence')}</strong></div><p>{t('ask.sampleSources')}</p></section>
                </div>
              </article>}
              {vercelDemo && !hasConversation && demoAnswers.map((sample) => <article key={sample.id} className='forge-message is-assistant'>
                <div className='forge-message-meta'><span className='forge-avatar'>F</span><span>{t('ask.assistant')}</span><em className='is-grounded'>{t('ask.sampleLabel')}</em></div>
                <div className='forge-message-card'>
                  <p className='forge-answer-label'>{t(sample.questionKey)}</p>
                  <p className='forge-answer-text'>{t(sample.answerKey)}</p>
                  <section className='forge-evidence-block' aria-label={t('ask.sourceEvidence')}><div className='forge-evidence-heading'><strong>{t('ask.sourceEvidence')}</strong></div><p>{t(sample.sourcesKey)}</p></section>
                </div>
              </article>)}
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
                  <input ref={documentInput} type="file" className="forge-hidden-input" accept=".pdf,.xls,.xlsx,.csv,.pptx,.txt" onChange={(event) => handleFile('document', event)} />
                  <input ref={imageInput} type="file" className="forge-hidden-input" accept=".png,.jpg,.jpeg,.bmp,.webp" onChange={(event) => handleFile('image', event)} />
                </div>
                <label className="forge-sr-only" htmlFor="question-input">{t('ask.questionLabel')}</label>
                <textarea id="question-input" value={question} onChange={(event) => onQuestionChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSubmit(); } }} placeholder={t('ask.questionPlaceholder')} maxLength={500} disabled={isLoading} />
                <button type="submit" className="forge-send-button" aria-label={isLoading ? t('ask.working') : t('ask.ask')} disabled={isLoading || !question.trim()}><span>{isLoading ? t('ask.working') : t('ask.ask')}</span><ArrowUpIcon /></button>
              </form>
              <div className="forge-composer-footer"><span>{vercelDemo ? 'Upload documents or images for processing · Shift + Enter' : 'Attach image · Click a source to reference it · Shift + Enter'}</span><span>{uploadStatus ?? question.length + '/500'}</span></div>
            </footer>
          </section>
        </div>

        <aside className="ask-side">
          <SourceDetails documents={documents} response={latestResponse} referencedDocument={referencedDocument} onReferenceDocument={onReferenceDocument} />
          {latestResponse ? <RetrievalTrace response={latestResponse} /> : <section className="forge-side-card forge-trace-card"><p className="forge-eyebrow">{t('ask.retrievalTrace')}</p><p className="forge-trace-flow">{t('ask.traceFlow')}</p><p className="forge-side-helper">{t('ask.traceHelper')}</p></section>}
        </aside>
      </div>
    </div>
  );
}
