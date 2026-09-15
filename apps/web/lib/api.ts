import type {
  DocumentSummary,
  HealthResponse,
  QueryResponse,
  UploadResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_FORGE_API_URL ?? "http://127.0.0.1:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  const body = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(body.error?.message ?? "The API request failed.");
  }
  return body;
}

export function getHealth() {
  return request<HealthResponse>("/health");
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
  });
}
