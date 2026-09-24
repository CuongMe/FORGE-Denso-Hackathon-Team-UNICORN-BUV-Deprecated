import type {
  EvaluationDataset,
  EvaluationRun,
  QueryMetrics,
  DocumentSummary,
  HealthResponse,
  IngestionJob,
  QueryResponse,
  UploadResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_FORGE_API_URL ?? "http://127.0.0.1:8000/api";
let adminKey = "";

export function setAdminKey(value: string) {
  adminKey = value.trim();
}

export function getDocumentRawUrl(documentId: string) {
  return `${API_BASE}/documents/${encodeURIComponent(documentId)}/raw`;
}
export function getDocumentPreviewUrl(documentId: string) {
  return `${API_BASE}/documents/${encodeURIComponent(documentId)}/preview`;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 30_000): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (adminKey) headers.set("X-Forge-Admin-Key", adminKey);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The API did not respond before the upload timeout. Check that the FastAPI service is running.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
  const body = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(body.error?.message ?? "The API request failed.");
  }
  return body;
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function getMetrics() {
  return request<QueryMetrics>('/metrics');
}

export function getEvaluationDatasets() {
  return request<{ data: { id: EvaluationDataset; count: number; answerable: number; signed_off: number; pending_review: number }[] }>('/evaluations/datasets');
}

export function getEvaluations() {
  return request<{ data: EvaluationRun[] }>('/evaluations');
}

export function getEvaluation(id: string) {
  return request<EvaluationRun>('/evaluations/' + encodeURIComponent(id));
}

export function startEvaluation(dataset: EvaluationDataset, limit: number) {
  return request<EvaluationRun>('/evaluations', { method: 'POST', body: JSON.stringify({ dataset, limit }) });
}

export async function getDocuments() {
  const response = await request<{ data: DocumentSummary[] }>("/documents");
  return response.data;
}

export function askQuestion(question: string) {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/documents", {
    method: "POST",
    body: form,
  }, 120_000);
}

export function getIngestionJob(jobId: string) {
  return request<{ data: IngestionJob }>(
    "/ingestion/jobs/" + encodeURIComponent(jobId),
  ).then((response) => response.data);
}
