"use client";

import { useMemo, useState } from "react";

import type { DocumentSummary, HealthResponse } from "@/lib/types";

type GraphNodeType = "source" | "chunk" | "concept";
type GraphNode = { id: string; type: GraphNodeType; title: string; subtitle: string; left: number; top: number; detail: string };
type GraphEdge = { from: string; to: string; label: string; score: string };

type GraphWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
};

const graphNodes: GraphNode[] = [
  { id: "EHS-VN-004", type: "source", title: "EHS-VN-004", subtitle: "Source · 7 pages", left: 86, top: 52, detail: "Bilingual safety terms and zero-energy confirmation." },
  { id: "QUALITY-RESULTS", type: "source", title: "QUALITY-RESULTS", subtitle: "Source · 1 sheet", left: 552, top: 52, detail: "Inspection results that validate torque values." },
  { id: "M6-TORQUE", type: "concept", title: "M6 TORQUE", subtitle: "Concept · 12 mentions", left: 32, top: 194, detail: "Torque specification shared across the work instruction." },
  { id: "WI-ASSY-001", type: "source", title: "WI-ASSY-001", subtitle: "Selected source · PDF", left: 325, top: 221, detail: "Work instruction / assembly" },
  { id: "SAFETY-PROCEDURE", type: "concept", title: "SAFETY PROCEDURE", subtitle: "Concept · 8 mentions", left: 605, top: 194, detail: "Safety procedure linked to the cited factory process." },
  { id: "C-0003", type: "chunk", title: "C-0003", subtitle: "Chunk · page 1", left: 101, top: 344, detail: "Evidence chunk from the selected work instruction." },
  { id: "C-0004", type: "chunk", title: "C-0004", subtitle: "Chunk · page 3", left: 546, top: 344, detail: "Evidence chunk linked to the selected work instruction." },
];

const graphEdges: GraphEdge[] = [
  { from: "EHS-VN-004", to: "WI-ASSY-001", label: "SHARES TERMS", score: "0.86" },
  { from: "QUALITY-RESULTS", to: "WI-ASSY-001", label: "VALIDATES VALUES", score: "0.73" },
  { from: "M6-TORQUE", to: "WI-ASSY-001", label: "MENTIONS", score: "0.68" },
  { from: "SAFETY-PROCEDURE", to: "WI-ASSY-001", label: "RELATES", score: "0.64" },
  { from: "WI-ASSY-001", to: "C-0003", label: "CONTAINS", score: "1.00" },
  { from: "WI-ASSY-001", to: "C-0004", label: "CONTAINS", score: "1.00" },
];

export function GraphRail({ documents, health }: { documents: DocumentSummary[]; health: HealthResponse | null }) {
  return <div className="forge-rail-content forge-graph-rail"><div className="forge-rail-heading"><div><p className="forge-eyebrow">GRAPH VIEW</p><p className="forge-rail-helper">Explore indexed relationships.</p></div></div><div className="forge-rail-stat-grid"><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? "—"}</strong><span>CHUNKS</span></div></div><p className="forge-rail-subheading">SHOW ON GRAPH</p><div className="forge-rail-graph-filters"><div className="is-active"><i className="source" />SOURCES<strong>{health?.documents_count ?? documents.length}</strong></div><div><i className="chunk" />CHUNKS<strong>{health?.chunks_count ?? "—"}</strong></div><div><i className="concept" />CONCEPTS<strong>26</strong></div></div><p className="forge-rail-subheading">RELATIONSHIP KEY</p><div className="graph-rail-legend"><div><i className="source" />Source</div><div><i className="chunk" />Chunk</div><div><i className="concept" />Concept</div></div><p className="forge-rail-note">Select a node to inspect its connected evidence.</p><div className="forge-rail-scroll-hint">SCROLL TO BROWSE GRAPH</div></div>;
}

export function GraphWorkspace({ documents, health }: GraphWorkspaceProps) {
  const [selectedId, setSelectedId] = useState("WI-ASSY-001");
  const [search, setSearch] = useState("");
  const [visible, setVisible] = useState<Record<GraphNodeType, boolean>>({ source: true, chunk: true, concept: true });
  const selected = graphNodes.find((node) => node.id === selectedId) ?? graphNodes[3];
  const query = search.trim().toLowerCase();
  const visibleNodes = useMemo(() => graphNodes.filter((node) => visible[node.type] && (!query || (node.id + " " + node.title + " " + node.subtitle + " " + node.detail).toLowerCase().includes(query))), [query, visible]);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graphEdges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to));
  const nodePosition = new Map(graphNodes.map((node) => [node.id, node]));
  const relationships = graphEdges.filter((edge) => edge.from === selected.id || edge.to === selected.id);
  const nodeCount = (health?.documents_count ?? documents.length) + (health?.chunks_count ?? 49) + 26;
  const filters: Array<[GraphNodeType, string, number]> = [["source", "SOURCES", health?.documents_count ?? documents.length], ["chunk", "CHUNKS", health?.chunks_count ?? 49], ["concept", "CONCEPTS", 26]];

  return <div className="forge-workspace graph-workspace"><div className="forge-workspace-heading graph-heading"><div><p className="forge-eyebrow">GRAPH</p><h1>Corpus graph</h1><p className="forge-workspace-helper">See how sources, chunks, and concepts connect across the indexed corpus.</p></div><div className="forge-corpus-summary"><strong>{nodeCount}</strong><span>NODES</span></div></div><div className="graph-search-bar forge-search-bar"><span className="forge-search-icon">⌕</span><input aria-label="Search graph" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search sources, chunks, or concepts..." /><strong>{nodeCount} NODES</strong></div><div className="graph-filter-row\"><span className="graph-filter-label">FILTER BY TYPE</span><div className="graph-filter-group"><button type="button" className="forge-filter-chip is-active">ALL</button>{filters.map(([type, label, count]) => <label className="graph-filter-chip graph-layer-filter" key={type}><input type="checkbox" checked={visible[type]} onChange={() => setVisible((current) => ({ ...current, [type]: !current[type] }))} />{label} {count}</label>)}</div></div><div className="graph-layout"><section className="graph-canvas-scroll" aria-label="Evidence relationship graph"><div className="graph-canvas"><div className="graph-canvas-label">LIVE CORPUS VIEW <span>{health?.documents_count ?? documents.length} SOURCES · {health?.chunks_count ?? 49} CHUNKS</span></div><svg className="graph-edges" viewBox="0 0 730 520" aria-hidden="true">{visibleEdges.map((edge) => { const from = nodePosition.get(edge.from); const to = nodePosition.get(edge.to); if (!from || !to) return null; const x1 = from.left + 72; const y1 = from.top + 30; const x2 = to.left + 72; const y2 = to.top + 30; return <g key={edge.from + "-" + edge.to}><line className="graph-edge-line" x1={x1} y1={y1} x2={x2} y2={y2} /><text className="graph-edge-label" x={(x1 + x2) / 2 - 28} y={(y1 + y2) / 2 - 6}>{edge.label}</text></g>; })}</svg>{visibleNodes.map((node) => <button type="button" key={node.id} className={"graph-node " + node.type + (selected.id === node.id ? " is-selected" : "")} style={{ left: node.left, top: node.top }} onClick={() => setSelectedId(node.id)}><span className="graph-node-dot" /><span><span className="graph-node-title">{node.title}</span><span className="graph-node-subtitle">{node.subtitle}</span></span></button>)}</div></section><aside className="graph-details"><p className="forge-eyebrow">NODE DETAILS</p><span className="graph-detail-pill">{selected.type.toUpperCase()}</span><h2>{selected.title}</h2><p>{selected.subtitle.replace("Selected source · PDF", "PDF · 4 PAGES · 8 CHUNKS")}<br />{selected.detail}</p><div className="forge-relationship-list"><h3>RELATIONSHIPS</h3>{relationships.slice(0, 3).map((edge) => <div className="forge-relationship" key={edge.from + edge.to}><span>{edge.from === selected.id ? edge.to : edge.from}</span><span>{edge.score}</span><small>{edge.label}</small></div>)}</div><a className="forge-side-link" href="#document-preview">OPEN DOCUMENT PREVIEW&nbsp; ↗</a><a className="forge-side-link" href="#relationship-map">VIEW RELATIONSHIP MAP&nbsp; ↗</a><p className="forge-side-foot">Source details preserve page, region, and chunk links.</p></aside></div></div>;
}
