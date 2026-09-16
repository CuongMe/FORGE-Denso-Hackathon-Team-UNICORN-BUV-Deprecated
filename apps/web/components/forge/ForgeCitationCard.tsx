import type { Citation } from "@/lib/types";

export function ForgeCitationCard({ citation }: { citation: Citation }) {
  return (
    <article className="forge-citation" aria-label="Source citation">
      <div className="forge-citation-topline">
        <span>{citation.doc_id}</span>
        <span>Match {Math.round(citation.score * 100)}%</span>
      </div>
      <p className="forge-citation-name">{citation.source_name}</p>
      <p className="forge-citation-meta">
        {citation.pages.length ? `Page${citation.pages.length > 1 ? "s" : ""} ${citation.pages.join(", ")}` : "Page not recorded"} · {citation.region} · {citation.region_type} · <span>{citation.chunk_id}</span>
      </p>
      <blockquote>&ldquo;{citation.quote}&rdquo;</blockquote>
    </article>
  );
}
