"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";

import type { DocumentSummary, HealthResponse, QueryResponse } from "@/lib/types";

import { ForgeCitationCard } from "./ForgeCitationCard";
import { ArrowUpIcon, ImageIcon, PinIcon, UploadIcon } from "./ForgeIcons";
import { PromptTable, type PromptItem } from "./PromptTable";
import { RetrievalTrace } from "./RetrievalTrace";

export type AskMessage = {
  id: string;
  role: "user" | "assistant";
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
  prompts: readonly PromptItem[];
  onQuestionChange: (value: string) => void;
  onSubmit: (question?: string) => void;
  onUpload: (file: File, kind: "document" | "image") => Promise<void>;
  onReference: (docId: string) => void;
};

export function AskWorkspace({
  health,
  documents,
  messages,
  question,
  isLoading,
  connectionError,
  uploadStatus,
  prompts,
  onQuestionChange,
  onSubmit,
  onUpload,
  onReference,
}: AskWorkspaceProps) {
  const documentInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const [sourcePickerOpen, setSourcePickerOpen] = useState(false);

  function handleFile(kind: "document" | "image", event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void onUpload(file, kind);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className="forge-workspace ask-workspace">
      {connectionError && <div className="forge-connection-alert" role="alert">{connectionError} Start the FastAPI service, then refresh.</div>}

      <div className="forge-workspace-heading forge-ask-heading">
        <div>
          <p className="forge-eyebrow">RAG CHAT BOX</p>
          <h1>Ask FORGE</h1>
        </div>
        <div className="forge-corpus-summary">
          <strong>{health?.chunks_count ?? "--"}</strong>
          <span>chunks / {health?.documents_count ?? (documents.length || "--")} sources</span>
        </div>
      </div>

      <PromptTable prompts={prompts} disabled={isLoading} onSelect={(value) => onSubmit(value)} />

      <section className="forge-conversation" aria-labelledby="conversation-heading" aria-live="polite" aria-busy={isLoading}>
        <div className="forge-conversation-heading"><span /><h2 id="conversation-heading">CONVERSATION</h2><span /></div>
        <div className="forge-message-list">
          {messages.map((message) => {
            const isUser = message.role === "user";
            const abstained = message.response?.abstained ?? false;
            return (
              <article key={message.id} className={`forge-message ${isUser ? "is-user" : "is-assistant"}`}>
                <div className="forge-message-meta"><span className="forge-avatar">{isUser ? "Y" : "F"}</span><span>{isUser ? "YOU" : "FORGE ASSISTANT"}</span>{abstained && <em>EVIDENCE UNAVAILABLE</em>}</div>
                <div className={`forge-message-card ${abstained ? "is-abstained" : ""}`}>
                  {message.content ? <p>{message.content}</p> : <p className="forge-loading"><i /><i /><i /> Ranking evidence and checking the answer threshold…</p>}
                  {message.response && !abstained && message.response.citations.length > 0 && (
                    <div className="forge-evidence-block">
                      <div className="forge-evidence-heading"><div><p className="forge-eyebrow">SOURCES DETAILS</p><span>Selected by hybrid retrieval and reranking.</span></div><RetrievalTrace response={message.response} /></div>
                      <div className="forge-citation-list">{message.response.citations.map((citation) => <ForgeCitationCard key={citation.chunk_id} citation={citation} />)}</div>
                    </div>
                  )}
                  {abstained && <p className="forge-abstention-note">No citation was returned because the evidence threshold was not met.</p>}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <footer className="forge-composer-wrap">
        <form className="forge-composer" onSubmit={handleSubmit}>
          <div className="forge-composer-tools">
            <button type="button" className="forge-icon-button" aria-label="Upload document" title="Upload document" onClick={() => documentInput.current?.click()} disabled={isLoading}><UploadIcon /></button>
            <button type="button" className="forge-icon-button" aria-label="Upload image" title="Upload image" onClick={() => imageInput.current?.click()} disabled={isLoading}><ImageIcon /></button>
            <div className="forge-source-picker-wrap">
              <button type="button" className={`forge-icon-button ${sourcePickerOpen ? "is-active" : ""}`} aria-label="Reference an indexed document" title="Reference an indexed document" aria-expanded={sourcePickerOpen} onClick={() => setSourcePickerOpen((open) => !open)} disabled={isLoading}><PinIcon /></button>
              {sourcePickerOpen && <div className="forge-source-picker" role="menu"><p>REFERENCE SOURCE</p>{documents.slice(0, 6).map((document) => <button key={document.doc_id} type="button" role="menuitem" onClick={() => { onReference(document.doc_id); setSourcePickerOpen(false); }}>{document.doc_id}<small>{document.format} · {document.factory_topic}</small></button>)}</div>}
            </div>
            <input ref={documentInput} type="file" className="forge-hidden-input" accept=".pdf,.xlsx,.csv" onChange={(event) => handleFile("document", event)} />
            <input ref={imageInput} type="file" className="forge-hidden-input" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => handleFile("image", event)} />
          </div>
          <label className="forge-sr-only" htmlFor="question-input">Ask FORGE about the indexed factory documents</label>
          <textarea id="question-input" value={question} onChange={(event) => onQuestionChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(); } }} placeholder="Ask about a process, measurement, or safety instruction…" maxLength={500} disabled={isLoading} />
          <button type="submit" className="forge-send-button" aria-label={isLoading ? "Working" : "Ask FORGE"} disabled={isLoading || !question.trim()}><span>{isLoading ? "Working" : "Ask"}</span><ArrowUpIcon /></button>
        </form>
        <div className="forge-composer-footer"><span>Enter to send · Shift + Enter for a new line</span><span>{uploadStatus ?? `${question.length}/500`}</span></div>
      </footer>
    </div>
  );
}
