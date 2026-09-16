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

function typeFor(document: DocumentSummary): Exclude<DocumentFilter, "ALL"> {
  const value = (document.format + " " + document.modality).toLowerCase();
  if (value.includes("image") || ["png", "jpg", "jpeg", "webp"].some((type) => value.includes(type))) return "IMAGE";
  if (value.includes("xlsx") || value.includes("excel")) return "XLSX";
  if (value.includes("csv")) return "CSV";
  return "PDF";
}

function labelFor(document: DocumentSummary) {
  return typeFor(document) === "IMAGE" ? "IMG" : typeFor(document);
}

function metadataFor(document: DocumentSummary, index: number) {
  const type = typeFor(document);
  if (type === "PDF") return { pages: (4 + index % 4) + " pages", chunks: String(8 + index % 7) };
  if (type === "IMAGE") return { pages: "6 images", chunks: "6" };
  if (type === "CSV") return { pages: "3 columns", chunks: "9" };
  return { pages: "1 sheet", chunks: "12" };
}

function RailFilters({ documents, active, onChange }: { documents: DocumentSummary[]; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  const filters: DocumentFilter[] = ["ALL", "PDF", "XLSX", "CSV", "IMAGE"];
  return <div className="forge-rail-filter-stack" aria-label="Filter documents by type">{filters.map((filter) => { const count = filter === "ALL" ? documents.length : documents.filter((document) => typeFor(document) === filter).length; return <button key={filter} type="button" className={"forge-rail-filter " + (active === filter ? "is-active" : "")} onClick={() => onChange(filter)}><span className={"forge-file-type-dot " + filter.toLowerCase()}>{filter === "ALL" ? <FileIcon /> : filter === "IMAGE" ? "IMG" : filter}</span>{filter === "ALL" ? "All sources" : filter === "IMAGE" ? "Images" : filter}<small>{count}</small></button>; })}</div>;
}

export function DocumentsRail({ documents, health, active, onChange }: { documents: DocumentSummary[]; health: HealthResponse | null; active: DocumentFilter; onChange: (filter: DocumentFilter) => void }) {
  return <div className="forge-rail-content forge-document-rail"><div className="forge-rail-heading"><div><p className="forge-eyebrow">DOCUMENT LIBRARY</p><p className="forge-rail-helper">{health?.chunks_count ?? "—"} chunks · ready</p></div><span className="forge-rail-count">{health?.documents_count ?? documents.length}<small>SOURCES</small></span></div><div className="forge-rail-stat-grid"><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? "—"}</strong><span>CHUNKS</span></div></div><p className="forge-rail-subheading">FILE TYPES</p><RailFilters documents={documents} active={active} onChange={onChange} /><div className="forge-index-health forge-rail-index-status"><p className="forge-eyebrow">INDEX STATUS</p><div className="forge-rail-status-card"><span className="forge-source-dot" /><div><strong>ALL SYSTEMS READY</strong><small>Last sync 2 min ago<br />0 pending sources</small></div></div></div><div className="forge-rail-scroll-hint">SCROLL TO BROWSE FILTERS</div></div>;
}

function Preview({ document, related }: { document: DocumentSummary | null; related: DocumentSummary[] }) {
  if (!document) return <aside className="forge-document-preview"><p className="forge-eyebrow">DOCUMENT PREVIEW</p><p className="forge-empty-copy">Select a source to inspect its metadata.</p></aside>;
  const type = typeFor(document);
  const meta = metadataFor(document, 0);
  return <aside className="forge-document-side"><section className="forge-document-preview"><div className="forge-preview-heading"><div><p className="forge-eyebrow">DOCUMENT PREVIEW</p><p className="forge-side-helper">Selected from document library</p></div><span className="forge-side-pill">INDEXED</span></div><div className="forge-current-reference forge-document-selected"><p className="forge-eyebrow">SELECTED DOCUMENT</p><strong>{document.doc_id}</strong><span>{document.factory_topic || "Work instruction / assembly"}</span><span>{type} · {meta.pages} · {meta.chunks} CHUNKS</span><span>INDEXED 2 MIN AGO</span><span>PAGE · TABLE · IMAGE</span><a href={"#" + document.doc_id}>OPEN DOCUMENT PREVIEW&nbsp; ↗</a></div><div className="forge-related-docs"><p className="forge-eyebrow">LINKED DOCUMENTS</p><p className="forge-side-helper">Related by content and provenance</p>{related.map((item, index) => <a href={"#" + item.doc_id} key={item.doc_id}><span>{item.doc_id}</span><span>{index === 0 ? "0.86" : "0.73"}</span></a>)}</div><a className="forge-side-link" href="#relationship-map">VIEW RELATIONSHIP MAP&nbsp; ↗</a></section><section className="forge-document-preview forge-index-health\"><p className="forge-eyebrow">INDEXING HEALTH</p><p className="forge-trace-flow">INGEST → PARSE → INDEX</p><div className="forge-health-list"><div><span className="forge-source-dot" />DOCUMENTS<strong>{document ? "READY" : "—"}</strong></div><div><span className="forge-source-dot blue" />CHUNKS<strong>INDEXED</strong></div><div><span className="forge-source-dot purple" />REVIEW QUEUE<strong>PENDING</strong></div></div><small className="forge-side-helper">Last sync 2 min ago</small></section></aside>;
}

export function DocumentsWorkspace({ documents, health, filter: controlledFilter, onFilterChange }: DocumentsWorkspaceProps) {
  const [internalFilter, setInternalFilter] = useState<DocumentFilter>("ALL");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.doc_id ?? null);
  const filter = controlledFilter ?? internalFilter;
  const setFilter = (nextFilter: DocumentFilter) => { setInternalFilter(nextFilter); onFilterChange?.(nextFilter); };
  const filteredDocuments = useMemo(() => { const query = search.trim().toLowerCase(); return documents.filter((document) => { const searchable = (document.doc_id + " " + document.source_name + " " + document.factory_topic + " " + document.language).toLowerCase(); return (filter === "ALL" || typeFor(document) === filter) && (!query || searchable.includes(query)); }); }, [documents, filter, search]);
  const selected = documents.find((document) => document.doc_id === selectedId) ?? filteredDocuments[0] ?? null;
  const selectedIndex = selected ? documents.findIndex((document) => document.doc_id === selected.doc_id) : -1;
  const related = selectedIndex >= 0 ? documents.filter((_, index) => index !== selectedIndex).slice(Math.max(0, selectedIndex - 1), Math.max(0, selectedIndex - 1) + 2) : [];

  return <div className="forge-workspace documents-workspace"><div className="forge-workspace-heading documents-heading"><div><p className="forge-eyebrow">DOCUMENTS</p><h1>Document library</h1><p className="forge-workspace-helper">Browse indexed sources, provenance, and ingestion status.</p></div><div className="forge-corpus-summary"><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div></div><div className="forge-search-bar"><SearchIcon /><input aria-label="Search documents" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search indexed documents..." /><strong>{filteredDocuments.length} SOURCES</strong></div><div className="forge-filter-row documents-filter-row" aria-label="Document type filters">{(["ALL", "PDF", "XLSX", "CSV", "IMAGE"] as DocumentFilter[]).map((item) => { const count = item === "ALL" ? documents.length : documents.filter((document) => typeFor(document) === item).length; return <button key={item} type="button" className={"forge-filter-chip " + (filter === item ? "is-active" : "")} onClick={() => setFilter(item)}>{item === "ALL" ? "ALL " : item + " "}{count}</button>; })}</div><div className="forge-document-layout"><section className="forge-document-table-card" aria-label="Indexed document table"><div className="forge-table-heading"><span>Showing {Math.min(filteredDocuments.length, 5)} of {documents.length || 0} documents · scroll for more</span></div><div className="forge-document-table-scroll"><table className="forge-document-table"><thead><tr><th>SOURCE</th><th>TYPE</th><th>PAGES / SHEETS</th><th>CHUNKS</th><th>STATUS</th></tr></thead><tbody>{filteredDocuments.map((document, index) => { const type = typeFor(document); const meta = metadataFor(document, index); return <tr id={document.doc_id} className={"forge-document-row " + (selected?.doc_id === document.doc_id ? "is-selected" : "")} key={document.doc_id} onClick={() => setSelectedId(document.doc_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedId(document.doc_id); }} tabIndex={0}><td className="forge-document-cell"><div className="forge-document-name"><span className={"forge-file-dot " + type.toLowerCase()}>{labelFor(document)}</span><div><strong>{document.doc_id}</strong><small>{document.factory_topic || "Factory operations source"}</small></div></div></td><td className="forge-document-cell">{type}</td><td className="forge-document-cell">{meta.pages}</td><td className="forge-document-cell"><strong>{meta.chunks}</strong></td><td className="forge-document-cell"><span className="forge-document-status">READY</span></td></tr>; })}{!filteredDocuments.length && <tr><td colSpan={5} className="forge-document-cell">No sources match this filter.</td></tr>}</tbody></table></div></section><Preview document={selected} related={related} /></div></div>;
}
