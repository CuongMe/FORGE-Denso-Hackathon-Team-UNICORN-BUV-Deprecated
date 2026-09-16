"use client";

import { useMemo, useState } from "react";

import type { DocumentSummary, HealthResponse } from "@/lib/types";

import { GraphIcon, SearchIcon } from "./ForgeIcons";

type GraphNodeType = "source" | "chunk" | "concept";
type GraphNode = { id: string; type: GraphNodeType; title: string; subtitle: string; left: number; top: number; detail: string };
type GraphEdge = { from: string; to: string; label: string };

type GraphWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
};

const graphNodes: GraphNode[] = [
  { id: "WI-ASSY-001", type: "source", title: "WI-ASSY-001", subtitle: "PDF · 4 pages", left: 50, top: 86, detail: "Assembly work instruction" },
  { id: "WI-ASSY-002", type: "source", title: "WI-ASSY-002", subtitle: "PDF · 6 pages", left: 50, top: 278, detail: "Torque verification" },
  { id: "chunk-041", type: "chunk", title: "chunk-041", subtitle: "page 2 · table", left: 300, top: 112, detail: "Torque sequence and target values" },
  { id: "chunk-083", type: "chunk", title: "chunk-083", subtitle: "page 4 · text", left: 300, top: 304, detail: "Inspection criteria and escalation" },
  { id: "torque-spec", type: "concept", title: "Torque specification", subtitle: "shared concept", left: 558, top: 80, detail: "The target torque required for the M6 bolts" },
  { id: "inspection", type: "concept", title: "Inspection gate", subtitle: "shared concept", left: 558, top: 268, detail: "A quality checkpoint linked to both instructions" },
];

const graphEdges: GraphEdge[] = [
  { from: "WI-ASSY-001", to: "chunk-041", label: "contains" },
  { from: "WI-ASSY-002", to: "chunk-083", label: "contains" },
  { from: "chunk-041", to: "torque-spec", label: "defines" },
  { from: "chunk-083", to: "inspection", label: "describes" },
  { from: "chunk-041", to: "inspection", label: "supports" },
];

function GraphRail({ documents, health }: { documents: DocumentSummary[]; health: HealthResponse | null }) {
  return (
    <>
      <div className="graph-rail-legend">
        <p className="forge-eyebrow">GRAPH LAYERS</p>
        {(["source", "chunk", "concept"] as GraphNodeType[]).map((type) => <div className="graph-toggle" key={type}><i className={type} /> {type === "source" ? "Sources" : type === "chunk" ? "Evidence chunks" : "Concepts"}</div>)}
      </div>
      <div className="forge-index-health"><p className="forge-eyebrow">INDEX HEALTH</p><p>{health?.chunks_count ?? "—"} chunks connect {documents.length} sources. Relationships are derived from indexed evidence and topic metadata.</p></div>
      <div className="forge-rail-section"><div className="forge-rail-section-heading"><div><p className="forge-eyebrow">GRAPH MODE</p><p className="forge-rail-helper">Inspect how a cited source relates to neighboring evidence.</p></div><GraphIcon className="forge-rail-icon" /></div></div>
    </>
  );
}

export function GraphWorkspace({ documents, health }: GraphWorkspaceProps) {
  const [selectedId, setSelectedId] = useState("chunk-041");
  const [search, setSearch] = useState("");
  const [visible, setVisible] = useState<Record<GraphNodeType, boolean>>({ source: true, chunk: true, concept: true });
  const selected = graphNodes.find((node) => node.id === selectedId) ?? graphNodes[0];
  const query = search.trim().toLowerCase();
  const visibleNodes = useMemo(() => graphNodes.filter((node) => visible[node.type] && (!query || `${node.id} ${node.title} ${node.subtitle} ${node.detail}`.toLowerCase().includes(query))), [query, visible]);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graphEdges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to));
  const nodePosition = new Map(graphNodes.map((node) => [node.id, node]));
  const relationships = graphEdges.filter((edge) => edge.from === selected.id || edge.to === selected.id).map((edge) => ({ label: edge.from === selected.id ? edge.to : edge.from, relationship: edge.label }));

  return (
    <div className="forge-workspace graph-workspace">
      <div className="forge-workspace-heading graph-heading"><div><p className="forge-eyebrow">SOURCE RELATIONSHIPS</p><h1>Graph</h1><p className="forge-workspace-helper">See how documents, structured chunks, and shared factory concepts connect around a cited answer.</p></div><div className="forge-corpus-summary"><strong>{health?.chunks_count ?? graphNodes.length}</strong><span>indexed chunks</span></div></div>
      <div className="graph-search-bar forge-search-bar"><SearchIcon /><input aria-label="Search graph" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search nodes or concepts" /></div>
      <div className="graph-filter-row"><div className="graph-filter-group"><span className="forge-filter-chip is-active">RELATIONSHIP VIEW</span><span className="forge-filter-chip">CITED CONTEXT</span></div><div className="graph-filter-group">{(["source", "chunk", "concept"] as GraphNodeType[]).map((type) => <label className="graph-toggle" key={type}><input type="checkbox" checked={visible[type]} onChange={() => setVisible((current) => ({ ...current, [type]: !current[type] }))} /> {type}</label>)}</div></div>
      <div className="graph-layout">
        <section className="graph-canvas-scroll" aria-label="Evidence relationship graph"><div className="graph-canvas"><div className="graph-canvas-label">DOCUMENT → CHUNK → CONCEPT</div><svg className="graph-edges" viewBox="0 0 730 520" aria-hidden="true">{visibleEdges.map((edge) => { const from = nodePosition.get(edge.from); const to = nodePosition.get(edge.to); if (!from || !to) return null; const x1 = from.left + 75; const y1 = from.top + 35; const x2 = to.left + 5; const y2 = to.top + 35; return <g key={`${edge.from}-${edge.to}`}><line className="graph-edge-line" x1={x1} y1={y1} x2={x2} y2={y2} /><text className="graph-edge-label" x={(x1 + x2) / 2 - 18} y={(y1 + y2) / 2 - 5}>{edge.label}</text></g>; })}</svg>{visibleNodes.map((node) => <button type="button" key={node.id} className={`graph-node ${node.type} ${selected.id === node.id ? "is-selected" : ""}`} style={{ left: node.left, top: node.top }} onClick={() => setSelectedId(node.id)}><span className="graph-node-dot" /><span><span className="graph-node-title">{node.title}</span><span className="graph-node-subtitle">{node.subtitle}</span></span></button>)}</div></section>
        <aside className="graph-details"><p className="forge-eyebrow">NODE DETAILS</p><h2>{selected.title}</h2><p>{selected.detail}</p><div className="graph-detail-meta"><div><span>Layer</span><strong>{selected.type}</strong></div><div><span>Evidence state</span><strong>indexed</strong></div><div><span>Source count</span><strong>{documents.length || "—"}</strong></div></div><div className="forge-relationship-list"><h3>RELATIONSHIPS</h3>{relationships.map((relationship) => <div className="forge-relationship" key={`${relationship.label}-${relationship.relationship}`}><span>{relationship.label}</span><span>{relationship.relationship}</span></div>)}</div></aside>
      </div>
    </div>
  );
}

export { GraphRail };
