"use client";

import { useMemo, useState } from "react";

import type { DocumentSummary, HealthResponse } from "@/lib/types";

import { FileIcon, SearchIcon } from "./ForgeIcons";

export type DocumentFilter = "ALL" | "PDF" | "XLSX" | "CSV" | "IMAGE";

type DocumentsWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  filter?: DocumentFilter;
  onFilterChange?: (filter: DocumentFilter) => void;
};

function formatKey(document: DocumentSummary): Exclude<DocumentFilter, "ALL"> {
  const value = `${document.format} ${document.modality}`.toLowerCase();
  if (value.includes("image") || ["png", "jpg", "jpeg", "webp"].some((type) => value.includes(type))) return "IMAGE";
  if (value.includes("xlsx") || value.includes("excel")) return "XLSX";
  if (value.includes("csv")) return "CSV";
  return "PDF";
}

function fileLabel(document: DocumentSummary) {
  return formatKey(document) === "IMAGE" ? "IMG" : formatKey(document);
}

function RailFilters({ documents, active, onChange }: { documents: DocumentSummary[]; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  const filters: DocumentFilter[] = ["ALL", "PDF", "XLSX", "CSV", "IMAGE"];
  return (
    <div className="forge-rail-filter-stack" aria-label="Filter documents by type">
      {filters.map((filter) => {
        const count = filter === "ALL" ? documents.length : documents.filter((document) => formatKey(document) === filter).length;
        return (
          <button key={filter} type="button" className={`forge-rail-filter ${active === filter ? "is-active" : ""}`} onClick={() => onChange(filter)}>
            <span className={`forge-file-type-dot ${filter.toLowerCase()}`}>{filter === "ALL" ? <FileIcon /> : filter.slice(0, 3)}</span>
            {filter === "ALL" ? "All sources" : filter === "IMAGE" ? "Images" : filter}
            <small>{count}</small>
          </button>
        );
      })}
    </div>
  );
}

function Preview({ document, related }: { document: DocumentSummary | null; related: DocumentSummary[] }) {
  if (!document) {
    return <aside className="forge-document-preview"><p className="forge-eyebrow">DOCUMENT PREVIEW</p><p className="forge-empty-copy">Select a source to inspect its metadata and relationships.</p></aside>;
  }
  const type = formatKey(document);
  return (
    <aside className="forge-document-preview">
      <div className="forge-preview-heading"><p className="forge-eyebrow">DOCUMENT PREVIEW</p><span className={`forge-preview-type ${type.toLowerCase()}`}>{fileLabel(document)}</span></div>
      <div className="forge-preview-card">
        <h2>{document.source_name}</h2>
        <p>{document.factory_topic || "Factory operations source"} · {document.language || "Unknown language"}</p>
        <dl className="forge-preview-meta">
          <div><dt>Document ID</dt><dd>{document.doc_id}</dd></div>
          <div><dt>Format</dt><dd>{type}</dd></div>
          <div><dt>Modality</dt><dd>{document.modality || "document"}</dd></div>
          <div><dt>Index state</dt><dd className="forge-document-status">READY</dd></div>
        </dl>
        <div className="forge-preview-actions"><button type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>FOCUS SOURCE</button><span className="forge-muted-label">PROVENANCE PRESERVED</span></div>
        <div className="forge-related-docs"><h3>RELATED DOCUMENTS</h3>{related.length ? related.map((item) => <a href={`#${item.doc_id}`} key={item.doc_id}><span>{item.doc_id}</span><span>{formatKey(item)}</span></a>) : <p className="forge-empty-copy">No related sources in this collection.</p>}</div>
      </div>
    </aside>
  );
}

export function DocumentsWorkspace({ documents, health, filter: controlledFilter, onFilterChange }: DocumentsWorkspaceProps) {
  const [internalFilter, setInternalFilter] = useState<DocumentFilter>("ALL");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.doc_id ?? null);
  const filter = controlledFilter ?? internalFilter;
  const setFilter = (nextFilter: DocumentFilter) => {
    setInternalFilter(nextFilter);
    onFilterChange?.(nextFilter);
  };

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const matchesFilter = filter === "ALL" || formatKey(document) === filter;
      const searchable = `${document.doc_id} ${document.source_name} ${document.factory_topic} ${document.language}`.toLowerCase();
      return matchesFilter && (!query || searchable.includes(query));
    });
  }, [documents, filter, search]);

  const selected = documents.find((document) => document.doc_id === selectedId) ?? filteredDocuments[0] ?? null;
  const selectedIndex = selected ? documents.findIndex((document) => document.doc_id === selected.doc_id) : -1;
  const related = selectedIndex >= 0 ? documents.filter((_, index) => index !== selectedIndex).slice(Math.max(0, selectedIndex - 1), Math.max(0, selectedIndex - 1) + 3) : [];
  const imageCount = documents.filter((document) => formatKey(document) === "IMAGE").length;
  const tabularCount = documents.filter((document) => ["CSV", "XLSX"].includes(formatKey(document))).length;

  return (
    <div className="forge-workspace documents-workspace">
      <div className="forge-workspace-heading documents-heading"><div><p className="forge-eyebrow">DOCUMENT LIBRARY</p><h1>Sources</h1><p className="forge-workspace-helper">Browse every indexed source with its file type, language, topic, and provenance state visible at a glance.</p></div><div className="forge-corpus-summary"><strong>{filteredDocuments.length}</strong><span>visible sources</span></div></div>
      <div className="forge-stat-grid"><div className="forge-stat-card"><span>Indexed sources</span><strong>{health?.documents_count ?? documents.length}</strong></div><div className="forge-stat-card"><span>Structured tables</span><strong>{tabularCount}</strong></div><div className="forge-stat-card"><span>Visual sources</span><strong>{imageCount}</strong></div></div>
      <div className="forge-search-bar"><SearchIcon /><input aria-label="Search documents" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search source name, topic, language, or document ID" /></div>
      <div className="forge-filter-row" aria-label="Document type filters">{(["ALL", "PDF", "XLSX", "CSV", "IMAGE"] as DocumentFilter[]).map((item) => <button key={item} type="button" className={`forge-filter-chip ${filter === item ? "is-active" : ""}`} onClick={() => setFilter(item)}>{item === "ALL" ? "All" : item === "IMAGE" ? "Images" : item}</button>)}</div>
      <div className="forge-document-layout">
        <section className="forge-document-table-card" aria-label="Indexed document table">
          <div className="forge-document-table-scroll"><table className="forge-document-table"><thead><tr><th>Source</th><th>Format</th><th>Language</th><th>Topic</th><th>State</th></tr></thead><tbody>{filteredDocuments.map((document) => { const type = formatKey(document); return <tr id={document.doc_id} className={`forge-document-row ${selected?.doc_id === document.doc_id ? "is-selected" : ""}`} key={document.doc_id} onClick={() => setSelectedId(document.doc_id)}><td className="forge-document-cell"><div className="forge-document-name"><span className={`forge-file-dot ${type.toLowerCase()}`}>{fileLabel(document)}</span><span title={document.source_name}>{document.doc_id}</span></div></td><td className="forge-document-cell">{type}</td><td className="forge-document-cell">{document.language || "—"}</td><td className="forge-document-cell">{document.factory_topic || "General operations"}</td><td className="forge-document-cell"><span className="forge-document-status">READY</span></td></tr>; })}{!filteredDocuments.length && <tr><td colSpan={5} className="forge-document-cell">No sources match this filter.</td></tr>}</tbody></table></div>
        </section>
        <Preview document={selected} related={related} />
      </div>
      <div className="forge-composer-footer"><span>CSV and image sources remain separate so their provenance is easy to inspect.</span><span>{filteredDocuments.length} / {documents.length || 0}</span></div>
    </div>
  );
}

export { RailFilters };
