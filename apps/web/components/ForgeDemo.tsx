"use client";

import { useEffect, useMemo, useState, type SVGProps } from "react";

import { askQuestion, getDocuments, getHealth, uploadDocument } from "@/lib/api";
import { demoQueries } from "@/lib/demo-queries";
import type { DocumentSummary, HealthResponse, QueryResponse } from "@/lib/types";

import { CitationCard } from "./CitationCard";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: QueryResponse;
};

const welcomeMessage: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Ask me about the indexed factory documents. I will show the evidence I used, or say I don't know when the corpus cannot support an answer.",
};

function newId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatLatency(value: number) {
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

function ArrowUpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M10 15V5M6 9l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function BookIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M4.5 4.25A2.25 2.25 0 0 1 6.75 2H16v13.75H6.75a2.25 2.25 0 0 0-2.25 2.25V4.25Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4.5 4.25A2.25 2.25 0 0 1 6.75 6.5H16M4.5 18h11.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GlobeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <circle cx="10" cy="10" r="7.5" />
      <path d="M2.75 10h14.5M10 2.5c2 2.1 3 4.6 3 7.5s-1 5.4-3 7.5c-2-2.1-3-4.6-3-7.5s1-5.4 3-7.5Z" strokeLinecap="round" />
    </svg>
  );
}

function SearchIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <circle cx="8.75" cy="8.75" r="5.25" />
      <path d="m12.75 12.75 4 4" strokeLinecap="round" />
    </svg>
  );
}

function ShieldIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M10 2.5 16 5v4.2c0 3.7-2.5 6.9-6 8.3-3.5-1.4-6-4.6-6-8.3V5l6-2.5Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m7.2 10 1.8 1.8 3.8-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UploadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M10 13V4M6.5 7.5 10 4l3.5 3.5M4 12.75v1.5A2.75 2.75 0 0 0 6.75 17h6.5A2.75 2.75 0 0 0 16 14.25v-1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatusDot({ warning = false }: { warning?: boolean }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${warning ? "bg-amber" : "bg-cyan pulse-dot"}`} aria-hidden="true" />;
}

function DemoPrompt({
  label,
  description,
  question,
  index,
  disabled,
  onClick,
}: {
  label: string;
  description: string;
  question: string;
  index: number;
  disabled: boolean;
  onClick: () => void;
}) {
  const Icon = index === 1 ? GlobeIcon : index === 2 ? ShieldIcon : SearchIcon;

  return (
    <button
      type="button"
      className="group relative overflow-hidden rounded-xl border border-line bg-panel/75 p-4 text-left transition duration-200 hover:-translate-y-0.5 hover:border-cyan/70 hover:bg-panel-strong disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
      onClick={onClick}
      disabled={disabled}
    >
      <span className="absolute right-0 top-0 h-20 w-20 translate-x-8 -translate-y-8 rounded-full bg-cyan/10 blur-2xl transition group-hover:bg-cyan/20" aria-hidden="true" />
      <span className="relative flex items-start justify-between gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-cyan/25 bg-cyan/10 text-cyan">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <span className="data-mono pt-1 text-[10px] font-semibold tracking-[0.14em] text-muted">0{index + 1}</span>
      </span>
      <span className="relative mt-4 block text-[10px] font-bold uppercase tracking-[0.16em] text-cyan">{label}</span>
      <span className="relative mt-2 block text-sm font-semibold leading-5 text-copy">{description}</span>
      <span className="relative mt-3 block text-xs leading-5 text-muted transition group-hover:text-copy/75">{question}</span>
    </button>
  );
}

function CorpusItem({ document }: { document: DocumentSummary }) {
  return (
    <div className="group rounded-lg border border-line/80 bg-ink/35 px-3 py-3 transition hover:border-cyan/45 hover:bg-ink/60">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan/70" aria-hidden="true" />
          <span className="truncate text-xs font-semibold text-copy">{document.doc_id}</span>
        </div>
        <span className="shrink-0 rounded bg-panel-strong px-1.5 py-1 text-[9px] font-bold uppercase tracking-[0.1em] text-muted">{document.format}</span>
      </div>
      <p className="mt-2 truncate pl-3.5 text-xs text-muted">{document.factory_topic}</p>
    </div>
  );
}

export function ForgeDemo() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([getHealth(), getDocuments()])
      .then(([healthResponse, documentResponse]) => {
        if (!mounted) return;
        setHealth(healthResponse);
        setDocuments(documentResponse);
        setConnectionError(null);
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        setConnectionError(error instanceof Error ? error.message : "The API is offline.");
      });

    return () => {
      mounted = false;
    };
  }, []);

  const visibleDocuments = useMemo(() => documents.slice(0, 6), [documents]);
  const apiState = connectionError ? "Needs attention" : health ? "Operational" : "Connecting";
  const apiWarning = Boolean(connectionError || !health);

  async function submitQuestion(value = question) {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;

    const assistantId = newId("assistant");
    setQuestion("");
    setIsLoading(true);
    setConnectionError(null);
    setMessages((current) => [
      ...current,
      { id: newId("user"), role: "user", content: trimmed },
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      const response = await askQuestion(trimmed);
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? { ...message, content: response.answer, response }
            : message,
        ),
      );
    } catch (error: unknown) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: error instanceof Error ? error.message : "The query could not be completed.",
              }
            : message,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setUploadStatus(`Uploading ${file.name}...`);
    try {
      const result = await uploadDocument(file);
      setUploadStatus(`${result.filename} received for ingestion.`);
    } catch (error: unknown) {
      setUploadStatus(error instanceof Error ? error.message : "Upload failed.");
    }
  }

  return (
    <main className="min-h-screen bg-ink text-copy">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col lg:flex-row">
        <aside className="border-b border-line/80 bg-panel/60 px-5 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-[324px] lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r lg:px-6 lg:py-7">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-cyan text-lg font-black text-ink shadow-[0_0_28px_rgba(118,224,193,0.16)]">F</div>
              <div>
                <p className="text-sm font-bold tracking-[0.22em] text-cyan">FORGE</p>
                <p className="mt-0.5 text-xs text-muted">Factory intelligence</p>
              </div>
            </div>
            <span className="data-mono text-[10px] font-semibold tracking-[0.12em] text-muted">v0.1</span>
          </div>

          <div className="mt-8 rounded-xl border border-cyan/30 bg-cyan/[0.07] p-4 panel-shadow">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan">Live demo goal</p>
              <span className="rounded-full border border-cyan/25 px-2 py-1 text-[9px] font-bold uppercase tracking-[0.12em] text-cyan">90 sec</span>
            </div>
            <p className="mt-4 text-sm font-medium leading-6 text-copy">Retrieve the right evidence, cite the source, and know when to stop.</p>
            <div className="mt-4 flex items-center gap-2 text-xs text-muted">
              <StatusDot />
              <span>Grounded response mode</span>
            </div>
          </div>

          <div className="mt-8">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted">Indexed corpus</h2>
                <p className="mt-1 text-xs text-muted/70">Sources available to retrieval</p>
              </div>
              <span className="data-mono rounded-full border border-line bg-ink/40 px-2 py-1 text-[10px] text-cyan">{health?.chunks_count ?? "--"} chunks</span>
            </div>
            <div className="mt-4 space-y-2">
              {visibleDocuments.map((document) => <CorpusItem key={document.doc_id} document={document} />)}
              {documents.length > visibleDocuments.length && <p className="px-1 text-xs text-muted">+ {documents.length - visibleDocuments.length} more source files</p>}
              {!documents.length && <p className="rounded-lg border border-dashed border-line px-3 py-4 text-xs leading-5 text-muted">Loading the document collection...</p>}
            </div>
          </div>

          <div className="mt-8 border-t border-line/80 pt-6">
            <div className="flex items-center gap-2">
              <BookIcon className="h-4 w-4 text-cyan" aria-hidden="true" />
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted" htmlFor="document-upload">Add a document</label>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line bg-ink/35 px-3 py-3 transition hover:border-cyan/60 hover:bg-ink/60 focus-within:border-cyan/70 focus-within:ring-2 focus-within:ring-cyan/20" htmlFor="document-upload">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-cyan/10 text-cyan"><UploadIcon className="h-4 w-4" aria-hidden="true" /></span>
              <span className="min-w-0">
                <span className="block truncate text-xs font-semibold text-copy">Choose source file</span>
                <span className="mt-1 block text-[10px] text-muted">PDF, image, CSV, or XLSX</span>
              </span>
              <input id="document-upload" className="sr-only" type="file" accept=".pdf,.png,.jpg,.jpeg,.xlsx,.csv" onChange={(event) => handleUpload(event.target.files?.[0])} />
            </label>
            <p className="mt-3 rounded-lg bg-ink/30 px-3 py-2 text-[11px] leading-5 text-muted">AI-generated synthetic, non-confidential hackathon corpus.</p>
            {uploadStatus && <p className="mt-2 text-xs text-cyan" role="status">{uploadStatus}</p>}
          </div>
        </aside>

        <section className="surface-grid flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="border-b border-line/80 bg-ink/75 px-5 py-6 backdrop-blur-sm lg:px-10 lg:py-8">
            <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-6">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <p className="data-mono text-[10px] font-bold uppercase tracking-[0.2em] text-cyan">Operations retrieval / 01</p>
                  <span className="inline-flex items-center gap-2 rounded-full border border-line bg-panel/70 px-2.5 py-1 text-[10px] font-semibold text-muted">
                    <StatusDot warning={apiWarning} />
                    {apiState}
                  </span>
                </div>
                <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.03em] text-copy sm:text-4xl">Ask the factory corpus.</h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">Multimodal evidence, ranked context, and an honest answer when the documents do not know.</p>
              </div>
              <div className="hidden min-w-[170px] rounded-xl border border-line bg-panel/65 px-4 py-3 sm:block">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted">Indexed context</p>
                <p className="data-mono mt-2 text-xl font-semibold text-copy">{health?.chunks_count ?? "--"}<span className="ml-1 text-xs font-normal text-muted">chunks</span></p>
                <p className="mt-1 text-[11px] text-muted">{health?.documents_count ?? (documents.length || "--")} source files</p>
              </div>
            </div>
          </header>

          <div className="flex-1 px-5 py-6 lg:px-10 lg:py-9">
            {connectionError && <div className="mx-auto mb-6 max-w-6xl rounded-xl border border-amber/50 bg-amber/10 px-4 py-3 text-sm text-amber" role="alert">{connectionError} Start the FastAPI service, then refresh this page.</div>}

            <div className="mx-auto max-w-6xl">
              <section aria-labelledby="demo-prompts-heading">
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan">Start with a proof point</p>
                    <h2 id="demo-prompts-heading" className="mt-1 text-base font-semibold text-copy">Three questions, three system behaviors</h2>
                  </div>
                  <p className="text-xs text-muted">Select a prompt to run the live path</p>
                </div>
                <div className="grid gap-3 md:grid-cols-3" aria-label="Demo questions">
                  {demoQueries.map((demo, index) => <DemoPrompt key={demo.label} {...demo} index={index} disabled={isLoading} onClick={() => void submitQuestion(demo.question)} />)}
                </div>
              </section>

              <section className="mt-10" aria-labelledby="conversation-heading" aria-live="polite" aria-busy={isLoading}>
                <div className="mb-4 flex items-center gap-3">
                  <span className="h-px flex-1 bg-line/70" />
                  <h2 id="conversation-heading" className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Conversation</h2>
                  <span className="h-px flex-1 bg-line/70" />
                </div>
                <div className="space-y-5">
                  {messages.map((message) => {
                    const isUser = message.role === "user";
                    const isAbstained = message.response?.abstained;

                    return (
                      <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                        <div className={`${isUser ? "max-w-xl" : "w-full max-w-4xl"}`}>
                          <div className={`mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] ${isUser ? "justify-end text-blue" : "text-cyan"}`}>
                            <span className={`grid h-5 w-5 place-items-center rounded-md text-[9px] ${isUser ? "bg-blue/15 text-blue" : "bg-cyan/15 text-cyan"}`}>{isUser ? "YU" : "F"}</span>
                            <span>{isUser ? "You" : "FORGE assistant"}</span>
                            {isAbstained && <span className="rounded-full border border-amber/35 px-2 py-0.5 text-[9px] text-amber">Evidence unavailable</span>}
                          </div>
                          <div className={`rounded-xl border px-5 py-4 text-sm leading-7 panel-shadow ${isUser ? "border-blue/35 bg-blue/[0.08] text-copy" : isAbstained ? "border-amber/50 bg-amber/[0.08] text-copy" : "border-line bg-panel/85 text-copy"}`}>
                            {message.content ? <p>{message.content}</p> : <div className="flex items-center gap-3 text-muted" role="status"><span className="flex gap-1" aria-hidden="true"><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan [animation-delay:-0.2s]" /><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan [animation-delay:-0.1s]" /><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan" /></span>Ranking evidence and checking the answer threshold...</div>}
                            {message.response && !isAbstained && message.response.citations.length > 0 && (
                              <div className="mt-5 border-t border-line/80 pt-4">
                                <div className="flex flex-wrap items-end justify-between gap-3">
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className="h-1.5 w-1.5 rounded-full bg-cyan" aria-hidden="true" />
                                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan">Evidence trail</p>
                                      <span className="rounded-full border border-cyan/25 bg-cyan/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-cyan">verified context</span>
                                    </div>
                                    <p className="mt-1 text-xs text-muted">Sources selected by hybrid retrieval and reranking</p>
                                  </div>
                                  <div className="data-mono flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted">
                                    <span>{message.response.trace.reranked_count} reranked</span>
                                    <span>{formatLatency(message.response.trace.latency_ms)}</span>
                                  </div>
                                </div>
                                <div className="mt-3 space-y-2">{message.response.citations.map((citation) => <CitationCard key={citation.chunk_id} citation={citation} />)}</div>
                              </div>
                            )}
                            {isAbstained && <p className="mt-4 border-t border-amber/30 pt-3 text-xs leading-5 text-amber">No citation was returned because the evidence threshold was not met.</p>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>
          </div>

          <footer className="border-t border-line/80 bg-ink/80 px-5 py-5 backdrop-blur-sm lg:px-10">
            <form className="mx-auto max-w-4xl" onSubmit={(event) => { event.preventDefault(); void submitQuestion(); }}>
              <div className="flex items-end gap-3 rounded-2xl border border-line bg-panel/90 p-2.5 transition focus-within:border-cyan/60 focus-within:ring-2 focus-within:ring-cyan/10">
                <span className="mb-1.5 ml-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-cyan/10 text-cyan"><SearchIcon className="h-4 w-4" aria-hidden="true" /></span>
                <label className="sr-only" htmlFor="question-input">Ask the factory corpus</label>
                <textarea
                  id="question-input"
                  className="min-h-11 flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 text-copy placeholder:text-muted focus:outline-none"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submitQuestion(); } }}
                  placeholder="Ask about a process, measurement, or safety instruction..."
                  maxLength={500}
                  disabled={isLoading}
                />
                <button type="submit" className="inline-flex items-center gap-2 rounded-xl bg-cyan px-4 py-3 text-sm font-bold text-ink transition hover:bg-copy disabled:cursor-not-allowed disabled:opacity-50" disabled={isLoading || !question.trim()}>
                  <span className="hidden sm:inline">{isLoading ? "Working" : "Ask"}</span>
                  <ArrowUpIcon className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap justify-between gap-2 px-1 text-[11px] text-muted">
                <span>Enter to send <span className="text-line">/</span> Shift + Enter for a new line</span>
                <span className="data-mono">{question.length}/500</span>
              </div>
            </form>
          </footer>
        </section>
      </div>
    </main>
  );
}
