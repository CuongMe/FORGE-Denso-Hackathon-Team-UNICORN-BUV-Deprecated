"use client";

import { useEffect, useState } from "react";

import { askQuestion, getDocuments, getHealth, getIngestionJob, uploadDocument } from "@/lib/api";
import { demoQueries } from "@/lib/demo-queries";
import type { DocumentSummary, HealthResponse, IngestionJob } from "@/lib/types";

import { AskWorkspace, type AskMessage } from "./forge/AskWorkspace";
import { DocumentsRail, DocumentsWorkspace, type DocumentFilter } from "./forge/DocumentsWorkspace";
import { ForgeRail } from "./forge/ForgeRail";
import { ForgeShell, type ForgeView } from "./forge/ForgeShell";
import { GraphWorkspace, GraphWorkspaceRail } from "./forge/GraphWorkspace";

const welcomeMessage: AskMessage = {
  id: "welcome",
  role: "assistant",
  content: "Ask me about the indexed factory documents. I will show the evidence I used, or say I don't know when the corpus cannot support an answer.",
};

const prompts = demoQueries;

function newId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function ForgeApp() {
  const [activeView, setActiveView] = useState<ForgeView>("ask");
  const [documentFilter, setDocumentFilter] = useState<DocumentFilter>("ALL");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [messages, setMessages] = useState<AskMessage[]>([welcomeMessage]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null);

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

  async function submitQuestion(value = question) {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;

    const assistantId = newId("assistant");
    setQuestion("");
    setIsLoading(true);
    setConnectionError(null);
    setMessages((current) => [...current, { id: newId("user"), role: "user", content: trimmed }, { id: assistantId, role: "assistant", content: "" }]);

    try {
      const response = await askQuestion(trimmed);
      setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: response.answer, response } : message));
    } catch (error: unknown) {
      setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: error instanceof Error ? error.message : "The query could not be completed." } : message));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload(file: File, kind: "document" | "image") {
    setUploadStatus("Uploading " + file.name + "...");
    try {
      const result = await uploadDocument(file);
      if (!result.job_id) {
        setIngestionJob(null);
        setUploadStatus(
          result.filename + (kind === "image" ? " received for image ingestion." : " received for ingestion."),
        );
        return;
      }

      setUploadStatus(result.filename + " queued. Waiting for the indexer...");
      setIngestionJob(result.job ?? null);
      let completed = result.job;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        completed = await getIngestionJob(result.job_id);
        setIngestionJob(completed);
        if (completed.status === "indexed" || completed.status === "failed") break;
        setUploadStatus(result.filename + " " + completed.stage + "...");
      }

      if (!completed || completed.status === "queued" || completed.status === "processing") {
        throw new Error("The upload is still processing. Check the document library shortly.");
      }
      if (completed.status === "failed") {
        throw new Error(completed.error ?? "Document ingestion failed.");
      }

      const [nextDocuments, nextHealth] = await Promise.all([getDocuments(), getHealth()]);
      setDocuments(nextDocuments);
      setHealth(nextHealth);
      const reviewCount = completed.result?.review_count ?? 0;
      setUploadStatus(
        result.filename + " indexed" + (reviewCount ? " with " + reviewCount + " visual review item(s)." : "."),
      );
    } catch (error: unknown) {
      setUploadStatus(error instanceof Error ? error.message : "Upload failed.");
    }
  }

  const rail = activeView === "ask" ? <ForgeRail documents={documents} health={health} eyebrow="SOURCE PREVIEW" helper="Indexed evidence available to chat" /> : activeView === "documents" ? <DocumentsRail documents={documents} health={health} active={documentFilter} onChange={setDocumentFilter} /> : <GraphWorkspaceRail documents={documents} health={health} />;

  return (
    <ForgeShell activeView={activeView} onViewChange={setActiveView} health={health} connectionError={connectionError} rail={rail}>
      {activeView === "ask" && <AskWorkspace health={health} documents={documents} messages={messages} question={question} isLoading={isLoading} connectionError={connectionError} uploadStatus={uploadStatus} ingestionJob={ingestionJob} prompts={prompts} onQuestionChange={setQuestion} onSubmit={(value) => void submitQuestion(value)} onUpload={handleUpload} onReference={(docId) => setQuestion((current) => `${current}${current ? " " : ""}@${docId} `)} />}
      {activeView === "documents" && <DocumentsWorkspace documents={documents} health={health} filter={documentFilter} onFilterChange={setDocumentFilter} />}
      {activeView === "graph" && <GraphWorkspace documents={documents} health={health} />}
    </ForgeShell>
  );
}
