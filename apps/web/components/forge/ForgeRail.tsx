import type { DocumentSummary, HealthResponse } from "@/lib/types";

import { FileIcon } from "./ForgeIcons";

type ForgeRailProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
  eyebrow: string;
  helper: string;
  children?: React.ReactNode;
};

export function ForgeRail({ documents, health, eyebrow, helper, children }: ForgeRailProps) {
  return (
    <div className="forge-rail-content">
      <div className="forge-rail-heading">
        <div>
          <p className="forge-eyebrow">{eyebrow}</p>
          <p className="forge-rail-helper">{helper}</p>
        </div>
        <span className="forge-rail-count">{health?.documents_count ?? (documents.length || "--")}</span>
      </div>
      {children}
      <div className="forge-rail-section forge-rail-sources">
        <div className="forge-rail-section-heading">
          <div>
            <p className="forge-eyebrow">INDEXED CORPUS</p>
            <p className="forge-rail-helper">{health?.chunks_count ?? "--"} chunks · ready</p>
          </div>
          <FileIcon className="forge-rail-icon" />
        </div>
        <div className="forge-source-list">
          {documents.slice(0, 5).map((document) => (
            <div className="forge-source-card" key={document.doc_id}>
              <span className="forge-source-dot" />
              <span className="forge-source-name">{document.doc_id}</span>
              <span className="forge-source-format">{document.format}</span>
            </div>
          ))}
          {!documents.length && <p className="forge-empty-copy">Loading source collection…</p>}
        </div>
      </div>
      <div className="forge-rail-scroll-hint">SCROLL TO BROWSE SOURCES</div>
    </div>
  );
}
