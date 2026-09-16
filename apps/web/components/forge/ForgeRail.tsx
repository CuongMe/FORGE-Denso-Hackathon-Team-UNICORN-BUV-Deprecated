import type { DocumentSummary, HealthResponse } from "@/lib/types";

import { FileIcon } from "./ForgeIcons";

type ForgeRailProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  eyebrow: string;
  helper: string;
};

export function ForgeRail({ documents, health, eyebrow, helper }: ForgeRailProps) {
  return <div className="forge-rail-content forge-ask-rail"><div className="forge-rail-heading"><div><p className="forge-eyebrow">{eyebrow}</p><p className="forge-rail-helper">{health?.documents_count ?? documents.length} source files · ready</p></div><span className="forge-rail-count">{health?.chunks_count ?? "—"}<small>CHUNKS</small></span></div><div className="forge-rail-stat-grid"><div><strong>{health?.chunks_count ?? "—"}</strong><span>CHUNKS</span></div><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div></div><div className="forge-rail-section forge-rail-sources"><div className="forge-rail-section-heading"><div><p className="forge-eyebrow">{eyebrow}</p><p className="forge-rail-helper">{helper}</p></div><FileIcon className="forge-rail-icon" /></div><div className="forge-source-list">{documents.slice(0, 3).map((document) => <div className="forge-source-card" key={document.doc_id}><span className="forge-source-dot" /><div className="forge-source-copy"><strong>{document.doc_id}</strong><small>{document.format} · {document.factory_topic || "factory source"}</small></div><span className="forge-source-format">{document.format.toUpperCase()}</span></div>)}{!documents.length && <p className="forge-empty-copy">Loading source collection...</p>}</div></div><div className="forge-rail-scroll-hint">SCROLL TO BROWSE ALL SOURCES</div></div>;
}
