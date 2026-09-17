'use client';

import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';

import type { DocumentSummary, HealthResponse, IngestionJob, QueryResponse } from '@/lib/types';

import { ArrowUpIcon, ImageIcon, PinIcon, UploadIcon } from './ForgeIcons';
import { PromptTable, type PromptItem } from './PromptTable';
import { RetrievalTrace } from './RetrievalTrace';
import { IngestionPipeline } from './IngestionPipeline';

export type AskMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  response?: QueryResponse;
};

type AskWorkspaceProps = {
  health: HealthResponse | null;
  documents: DocumentSummary[];
  messages: AskMessage[];
  question: string;
  isLoading: boolean;
  connectionError: string | null;
  uploadStatus: string | null;
  ingestionJob: IngestionJob | null;
  prompts: readonly PromptItem[];
  onQuestionChange: (value: string) => void;
  onSubmit: (question?: string) => void;
  onUpload: (file: File, kind: 'document' | 'image') => Promise<void>;
  onReference: (docId: string) => void;
};

function RelatedSource({ docId, label, score }: { docId: string; label: string; score: string }) {
  return <div className='forge-related-source'><span className='forge-related-dot' /><div><strong>{docId}</strong><small>{label}</small></div><b>{score}</b></div>;
}

function citationLocation(citation: QueryResponse['citations'][number] | null, format: string) {
  if (citation?.page != null) return 'PAGE ' + citation.page;
  if (citation?.pages.length) return 'PAGES ' + citation.pages.join(', ');
  return format === 'CSV' || format === 'XLSX' ? 'LOCATION NOT RECORDED' : 'PAGE NOT RECORDED';
}

function SourceDetails({ documents, response }: { documents: DocumentSummary[]; response: QueryResponse | null }) {
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
    <section className='forge-side-card forge-source-details'>
      <div className='forge-side-card-heading'><div><p className='forge-eyebrow'>SOURCE DETAILS</p><p className='forge-side-helper'>Current reference and linked documents</p></div><span className='forge-side-pill'>SELECTED IN CHAT</span></div>
      {current && citation ? <div className='forge-current-reference'>
        <p className='forge-eyebrow'>CURRENT CHAT REFERENCE</p>
        <strong>{current.doc_id}</strong>
        <span>{format} · {(current.factory_topic || 'WORK INSTRUCTION').toUpperCase()}</span>
        <span>{citationLocation(citation, format)} · {citation.region_type.toUpperCase()} · {citation.chunk_id}</span>
        <b>{citation.region}</b>
        <a href={'#' + current.doc_id}>OPEN REFERENCED REGION&nbsp; ↗</a>
      </div> : <div className='forge-current-reference is-empty'>
        <p className='forge-eyebrow'>CURRENT CHAT REFERENCE</p><strong>No source selected</strong><span>Ask a question to populate source details.</span>
      </div>}
      <div className='forge-side-section'>
        <p className='forge-eyebrow'>RELATED DOCUMENTS</p>
        <p className='forge-side-helper'>Linked by this answer&apos;s citations</p>
        <div className='forge-related-list'>{relatedDocuments.length ? relatedDocuments.map((item, index) => <RelatedSource key={item.docId + ':' + item.chunkId + ':' + index} docId={item.docId} label={item.label} score={item.score} />) : <p className='forge-empty-copy'>No related citation was returned for this answer.</p>}</div>
      </div>
      <a className='forge-side-link' href='#relationship-map'>VIEW RELATIONSHIP MAP&nbsp; ↗</a>
    </section>
  );
}

export function AskWorkspace({ health, documents, messages, question, isLoading, connectionError, uploadStatus, ingestionJob, prompts, onQuestionChange, onSubmit, onUpload, onReference }: AskWorkspaceProps) {
  const documentInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const [sourcePickerOpen, setSourcePickerOpen] = useState(false);
  let latestResponse: QueryResponse | null = null;
  messages.forEach((message) => { if (message.response) latestResponse = message.response; });

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
    <div className='forge-workspace ask-workspace'>
      {connectionError && <div className='forge-connection-alert' role='alert'>{connectionError} Start the FastAPI service, then refresh.</div>}
      <div className='ask-layout'>
        <div className='ask-primary'>
          <div className='forge-workspace-heading forge-ask-heading'><div><p className='forge-eyebrow'>RAG CHAT BOX</p><h1>Ask FORGE</h1></div><div className='forge-corpus-summary'><strong>{health?.chunks_count ?? '--'}</strong><span>CHUNKS / {health?.documents_count ?? (documents.length || '--')} SOURCES</span></div></div>
          <PromptTable prompts={prompts} disabled={isLoading} onSelect={(value) => onSubmit(value)} />
          <section className='forge-conversation' aria-labelledby='conversation-heading' aria-live='polite' aria-busy={isLoading}>
            <div className='forge-conversation-heading'><span /><h2 id='conversation-heading'>CONVERSATION</h2><span /></div>
            <div className='forge-message-list'>{messages.map((message) => {
              const isUser = message.role === 'user';
              const grounding = message.response?.grounding ?? (message.response?.abstained ? 'no_match' : 'grounded');
              const noMatch = grounding === 'no_match';
              const bestMatch = grounding === 'best_match';
              const statusLabel = noMatch ? 'NO MATCH' : bestMatch ? 'BEST MATCH' : 'GROUNDED';
              return <article key={message.id} className={'forge-message ' + (isUser ? 'is-user' : 'is-assistant')}><div className='forge-message-meta'><span className='forge-avatar'>{isUser ? 'Y' : 'F'}</span><span>{isUser ? 'YOU' : 'FORGE ASSISTANT'}</span>{!isUser && message.response && <em className={noMatch || bestMatch ? 'is-warning' : 'is-grounded'}>{statusLabel}</em>}</div><div className={'forge-message-card ' + (noMatch ? 'is-abstained' : '')}>{isUser ? <p>{message.content}</p> : message.content ? <><p className='forge-answer-label'>ANSWER</p><p className='forge-answer-text'>{message.content}</p>{message.response && !noMatch && <div className='forge-answer-footer'><span>{bestMatch ? 'Closest indexed evidence returned for this question.' : 'Evidence supports this answer from the indexed corpus.'}</span><span>{message.response.trace.latency_ms < 1000 ? Math.round(message.response.trace.latency_ms) + ' ms' : (message.response.trace.latency_ms / 1000).toFixed(1) + ' s'}</span></div>}{message.response && !noMatch && message.response.citations.length > 0 && <span className='forge-view-evidence'>VIEW EVIDENCE&nbsp; →</span>}{noMatch && <p className='forge-abstention-note'>No matching content was retrieved from the indexed corpus.</p>}</> : <p className='forge-loading'><i /><i /><i /> Ranking available evidence...</p>}</div></article>;
            })}</div>
          </section>
          <div className='forge-document-context'><strong>DOCUMENT CONTEXT</strong><span className='forge-context-pill'>ALL INDEXED DOCS</span><span>Type / to pin a specific source</span></div>
          <footer className='forge-composer-wrap'><form className='forge-composer' onSubmit={handleSubmit}><div className='forge-composer-tools'><button type='button' className='forge-icon-button' aria-label='Upload document' title='Upload document' onClick={() => documentInput.current?.click()} disabled={isLoading}><UploadIcon /></button><button type='button' className='forge-icon-button' aria-label='Upload image' title='Upload image' onClick={() => imageInput.current?.click()} disabled={isLoading}><ImageIcon /></button><div className='forge-source-picker-wrap'><button type='button' className={'forge-icon-button ' + (sourcePickerOpen ? 'is-active' : '')} aria-label='Reference an indexed document' title='Reference an indexed document' aria-expanded={sourcePickerOpen} onClick={() => setSourcePickerOpen((open) => !open)} disabled={isLoading}><PinIcon /></button>{sourcePickerOpen && <div className='forge-source-picker' role='menu'><p>REFERENCE SOURCE</p>{documents.slice(0, 6).map((document) => <button key={document.doc_id} type='button' role='menuitem' onClick={() => { onReference(document.doc_id); setSourcePickerOpen(false); }}>{document.doc_id}<small>{document.format} · {document.factory_topic}</small></button>)}</div>}</div><input ref={documentInput} type='file' className='forge-hidden-input' accept='.pdf,.xlsx,.csv' onChange={(event) => handleFile('document', event)} /><input ref={imageInput} type='file' className='forge-hidden-input' accept='.png,.jpg,.jpeg,.webp' onChange={(event) => handleFile('image', event)} /></div><label className='forge-sr-only' htmlFor='question-input'>Ask FORGE about the indexed factory documents</label><textarea id='question-input' value={question} onChange={(event) => onQuestionChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSubmit(); } }} placeholder='Ask about a process, measurement, or safety instruction...' maxLength={500} disabled={isLoading} /><button type='submit' className='forge-send-button' aria-label={isLoading ? 'Working' : 'Ask FORGE'} disabled={isLoading || !question.trim()}><span>{isLoading ? 'Working' : 'Ask'}</span><ArrowUpIcon /></button></form><div className='forge-composer-footer'><span>Attach image · Pin a document · Type / to reference sources · Shift + Enter</span><span>{uploadStatus ?? question.length + '/500'}</span></div><p className='forge-grounded-note'>GROUNDED BY DESIGN · CITATIONS ARE SERVER-OWNED</p>{ingestionJob && <IngestionPipeline job={ingestionJob} />}</footer>
        </div>
        <aside className='ask-side'><SourceDetails documents={documents} response={latestResponse} />{latestResponse ? <RetrievalTrace response={latestResponse} /> : <section className='forge-side-card forge-trace-card'><p className='forge-eyebrow'>RETRIEVAL TRACE</p><p className='forge-trace-flow'>HYBRID → RERANK → ANSWER</p><p className='forge-side-helper'>Run a question to inspect ranked candidate detail.</p></section>}</aside>
      </div>
    </div>
  );
}
