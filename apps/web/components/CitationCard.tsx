import type { Citation } from "@/lib/types";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <article className="rounded-lg border border-line/80 border-l-2 border-l-cyan bg-ink/55 px-4 py-3" aria-label="Source citation">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan">
        <span className="data-mono">{citation.doc_id}</span>
        <span className="rounded-full bg-cyan/10 px-2 py-1">Match {Math.round(citation.score * 100)}%</span>
      </div>
      <p className="mt-3 text-sm font-medium text-copy">{citation.source_name}</p>
      <p className="mt-1 text-[11px] text-muted">
        {citation.pages.length ? `Page${citation.pages.length > 1 ? "s" : ""} ${citation.pages.join(", ")}` : "Page not recorded"} / {citation.region} / {citation.region_type} / <span className="data-mono">{citation.chunk_id}</span>
      </p>
      <blockquote className="mt-3 border-t border-line/80 pt-3 text-sm leading-6 text-copy/80">
        &ldquo;{citation.quote}&rdquo;
      </blockquote>
    </article>
  );
}
