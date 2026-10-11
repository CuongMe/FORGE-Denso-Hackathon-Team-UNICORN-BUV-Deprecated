"use client";

import { useEffect, useState } from "react";

import { askQuestion, getDocuments, getHealth, getIngestionJob, uploadDocument } from "@/lib/api";
import { CHAT_HISTORY_KEY, parseChatHistory, upsertChatHistory, type ChatHistoryEntry } from "@/lib/chat-history";
import { demoQueries } from "@/lib/demo-queries";
import type { DocumentSummary, HealthResponse, IngestionJob } from "@/lib/types";

import { AskWorkspace, type AskMessage } from "./forge/AskWorkspace";
import { DocumentsRail, DocumentsWorkspace, type DocumentFilter } from "./forge/DocumentsWorkspace";
import { ForgeRail } from "./forge/ForgeRail";
import { ForgeShell, type ForgeView } from "./forge/ForgeShell";
import { EvaluationRail, EvaluationWorkspace } from "./forge/EvaluationWorkspace";
import { getMessages, type Language } from "@/lib/i18n";
import { getDemoUploadStages } from "@/lib/demo-upload";
import { NextIntlClientProvider, useTranslations } from "next-intl";

const VERCEL_DEMO = process.env.NEXT_PUBLIC_FORGE_VERCEL_DEMO === "1";

function welcomeMessage(t: (key: string) => string): AskMessage {
  return { id: "welcome", role: "assistant", content: t("ask.welcome") };
}

function newId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function pendingUploadJob(file: File): IngestionJob {
  const now = new Date().toISOString();
  return {
    job_id: newId('local-upload'),
    document_id: 'pending-upload',
    original_filename: file.name,
    status: 'processing',
    stage: 'uploading',
    attempts: 0,
    error: null,
    result: null,
    queued_at: now,
    started_at: now,
    completed_at: null,
    updated_at: now,
    progress: 0,
    stages: [],
  };
}

function ForgeAppContent({ language, onLanguageChange }: { language: Language; onLanguageChange: (language: Language) => void }) {
  const t = useTranslations();
  const [activeView, setActiveView] = useState<ForgeView>("ask");
  const [documentFilter, setDocumentFilter] = useState<DocumentFilter>("ALL");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [messages, setMessages] = useState<AskMessage[]>(() => [welcomeMessage(t)]);
  const [chatHistory, setChatHistory] = useState<ChatHistoryEntry[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [historyReady, setHistoryReady] = useState(false);
  const [question, setQuestion] = useState("");
  const [referencedDocumentId, setReferencedDocumentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const prompts = demoQueries.map((prompt, index) => ({
    label: prompt.nativeLanguage ? prompt.label : t(`prompt.${index}.label`),
    description: prompt.nativeLanguage ? prompt.description : t(`prompt.${index}.description`),
    question: prompt.nativeLanguage ? prompt.question : t(`prompt.${index}.question`),
    expectedAnswer: prompt.expectedAnswer ?? t(`prompt.${index}.answer`),
  }));

  useEffect(() => {
    setMessages((current) => current.length === 1 && current[0].id === "welcome" ? [welcomeMessage(t)] : current);
  }, [language, t]);

  useEffect(() => {
    try {
      setChatHistory(parseChatHistory(window.localStorage.getItem(CHAT_HISTORY_KEY)));
    } catch {
      setChatHistory([]);
    }
    setHistoryReady(true);
  }, []);

  useEffect(() => {
    if (!historyReady || !activeChatId) return;
    // shortcut: save transcript text only; persist evidence details if restoring citations becomes necessary.
    const transcript = messages.filter((message) => message.id !== "welcome").map(({ id, role, content }) => ({ id, role, content }));
    if (!transcript.length) return;
    const firstMessage = transcript.find((message) => message.role === "user") ?? transcript[0];
    setChatHistory((current) => upsertChatHistory(current, {
      id: activeChatId,
      title: firstMessage.content.replace(/\s+/g, " ").trim().slice(0, 80) || "Chat",
      updatedAt: new Date().toISOString(),
      messages: transcript,
    }));
  }, [messages, activeChatId, historyReady]);

  useEffect(() => {
    if (!historyReady) return;
    try {
      window.localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chatHistory));
    } catch {
      // The current chat remains usable if browser storage is unavailable or full.
    }
  }, [chatHistory, historyReady]);

  useEffect(() => {
    let mounted = true;
    let refreshInFlight = false;

    async function refreshCorpus() {
      if (!mounted || refreshInFlight) return;
      refreshInFlight = true;
      try {
        const [healthResponse, documentResponse] = await Promise.all([getHealth(), getDocuments()]);
        if (!mounted) return;
        setHealth(healthResponse);
        setDocuments(documentResponse);
        setConnectionError(null);
      } catch (error: unknown) {
        if (!mounted) return;
        setConnectionError(error instanceof Error ? error.message : t("api.offline"));
      } finally {
        refreshInFlight = false;
      }
    }

    void refreshCorpus();
    const refreshTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refreshCorpus();
    }, VERCEL_DEMO ? 60_000 : 5000);

    return () => {
      mounted = false;
      window.clearInterval(refreshTimer);
    };
  }, [language, t]);

  async function submitQuestion(value = question) {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;

    const assistantId = newId("assistant");
    setActiveChatId(activeChatId ?? newId("chat"));
    setQuestion("");
    setReferencedDocumentId(null);
    setIsLoading(true);
    setConnectionError(null);
    setMessages((current) => [...current, { id: newId("user"), role: "user", content: trimmed }, { id: assistantId, role: "assistant", content: "" }]);

    try {
      const response = await askQuestion(trimmed);
      setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: response.answer, response } : message));
    } catch (error: unknown) {
      setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: error instanceof Error ? error.message : t("ask.errorQuery") } : message));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload(file: File) {
    setActiveChatId(activeChatId ?? newId("chat"));
    let localJob = pendingUploadJob(file);
    if (VERCEL_DEMO) localJob = { ...localJob, job_id: newId('demo-upload') };
    const uploadMessageId = newId("upload");
    setMessages((current) => [...current, { id: uploadMessageId, role: "upload", content: file.name, ingestionJob: localJob }]);
    setUploadStatus(t("ask.uploading", { name: file.name }));

    if (VERCEL_DEMO) {
      const stages = getDemoUploadStages(file);
      for (const [index, stage] of stages.entries()) {
        await new Promise((resolve) => window.setTimeout(resolve, 450));
        const completed = stage === 'completed';
        localJob = {
          ...localJob,
          stage,
          status: completed ? 'indexed' : 'processing',
          progress: Math.round(((index + 1) / stages.length) * 100),
          updated_at: new Date().toISOString(),
          completed_at: completed ? new Date().toISOString() : null,
        };
        setMessages((current) => current.map((message) => message.id === uploadMessageId ? { ...message, ingestionJob: localJob } : message));
        setUploadStatus(completed ? t('ask.demoUploadComplete', { name: file.name }) : t('ask.processing', { name: file.name, stage: t('stage.' + stage) }));
      }
      return;
    }

    try {
      const result = await uploadDocument(file);
      setUploadStatus(t("ask.queued", { name: result.filename }));
      setMessages((current) => current.map((message) => message.id === uploadMessageId ? { ...message, content: result.filename, ingestionJob: result.job } : message));
      let completed = result.job;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        completed = await getIngestionJob(result.job_id);
        setMessages((current) => current.map((message) => message.id === uploadMessageId ? { ...message, ingestionJob: completed } : message));
        if (completed.status === "indexed" || completed.status === "failed") break;
        setUploadStatus(t("ask.processing", { name: result.filename, stage: t('stage.' + completed.stage) }));
      }

      if (!completed || completed.status === "queued" || completed.status === "processing") {
        throw new Error(t("ask.stillProcessing"));
      }
      if (completed.status === "failed") {
        throw new Error(completed.error ?? t("ask.ingestionFailed"));
      }

      const [nextDocuments, nextHealth] = await Promise.all([getDocuments(), getHealth()]);
      setDocuments(nextDocuments);
      setHealth(nextHealth);
      const reviewCount = completed.result?.review_count ?? 0;
      setUploadStatus(
        t("ask.indexed", { name: result.filename, suffix: reviewCount ? t("ask.reviewItems", { count: reviewCount }) : t("ask.indexedPeriod") }),
      );
    } catch (error: unknown) {
      setUploadStatus(error instanceof Error ? error.message : t("ask.uploadFailed"));
    }
  }

  function referenceDocument(docId: string) {
    setReferencedDocumentId(docId);
    setQuestion((current) => {
      const withoutDocumentReference = current.replace(/(^|\s)@[A-Za-z0-9][A-Za-z0-9_-]*/g, " ").trim();
      return `${withoutDocumentReference}${withoutDocumentReference ? " " : ""}@${docId} `;
    });
    window.requestAnimationFrame(() => document.getElementById("question-input")?.focus());
  }

  function clearDocumentReference() {
    setReferencedDocumentId(null);
    setQuestion((current) => current.replace(/(^|\s)@[A-Za-z0-9][A-Za-z0-9_-]*/g, " ").replace(/\s{2,}/g, " ").trim());
    window.requestAnimationFrame(() => document.getElementById("question-input")?.focus());
  }

  function clearChat() {
    setActiveChatId(null);
    setMessages([welcomeMessage(t)]);
    setQuestion("");
    setReferencedDocumentId(null);
    setUploadStatus(null);
  }

  function restoreChat(entry: ChatHistoryEntry) {
    setActiveChatId(entry.id);
    setMessages([welcomeMessage(t), ...entry.messages]);
    setQuestion("");
    setReferencedDocumentId(null);
    setUploadStatus(null);
  }

  function clearHistory() {
    setChatHistory([]);
    clearChat();
  }

  function handleQuestionChange(value: string) {
    setQuestion(value);
    const match = value.match(/(^|\s)@([A-Za-z0-9][A-Za-z0-9_-]*)/);
    setReferencedDocumentId(match && documents.some((document) => document.doc_id === match[2]) ? match[2] : null);
  }

  const rail = activeView === "ask" ? <ForgeRail documents={documents} health={health} eyebrow={t("rail.sources")} helper={t("rail.clickReference")} onReference={referenceDocument} /> : activeView === "documents" ? <DocumentsRail documents={documents} health={health} filter={documentFilter} onFilterChange={setDocumentFilter} /> : <EvaluationRail vercelDemo={VERCEL_DEMO} />;

  return (
    <ForgeShell activeView={activeView} onViewChange={setActiveView} health={health} connectionError={connectionError} rail={rail} language={language} onLanguageChange={onLanguageChange}>
      {activeView === "ask" && <AskWorkspace health={health} documents={documents} messages={messages} history={chatHistory} activeChatId={activeChatId} onRestoreChat={restoreChat} onClearHistory={clearHistory} question={question} referencedDocument={documents.find((document) => document.doc_id === referencedDocumentId) ?? null} isLoading={isLoading} connectionError={connectionError} uploadStatus={uploadStatus} prompts={prompts} onQuestionChange={handleQuestionChange} onSubmit={(value) => void submitQuestion(value)} onUpload={handleUpload} onReferenceDocument={referenceDocument} onClearReference={clearDocumentReference} onClearChat={clearChat} vercelDemo={VERCEL_DEMO} />}
        {activeView === "documents" && <DocumentsWorkspace documents={documents} filter={documentFilter} onFilterChange={setDocumentFilter} vercelDemo={VERCEL_DEMO} ingestionJobs={messages.flatMap((message) => message.ingestionJob ? [message.ingestionJob] : [])} />}
      {(activeView === 'metrics' || activeView === 'evaluations') && <EvaluationWorkspace mode={activeView} health={health} vercelDemo={VERCEL_DEMO} />}
    </ForgeShell>
  );
}

export function ForgeApp() {
  const [language, setLanguage] = useState<Language>("en");
  useEffect(() => { document.documentElement.lang = language; }, [language]);
  return <NextIntlClientProvider locale={language} timeZone='Asia/Ho_Chi_Minh' messages={getMessages(language)}><ForgeAppContent language={language} onLanguageChange={setLanguage} /></NextIntlClientProvider>;
}
