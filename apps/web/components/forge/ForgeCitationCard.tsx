import { useTranslations } from "next-intl";
import type { Citation } from "@/lib/types";

export function ForgeCitationCard({ citation }: { citation: Citation }) {
  const t = useTranslations();
  return (
    <article className="forge-citation" aria-label={t("citation.source")}>
      <div className="forge-citation-top">
        <span className="forge-citation-source" title={citation.source_name}>{citation.source_name}</span>
        <span className="forge-citation-score">{t("citation.match", { value: Math.round(citation.score * 100) })}</span>
      </div>
      <p className="forge-citation-meta">
        <span>{citation.pages.length ? t(citation.pages.length > 1 ? "citation.pages" : "citation.page", { value: citation.pages.join(", ") }) : t("citation.notRecorded")}</span>
        <span>{citation.region}</span>
        <span>{citation.region_type || t("citation.region")}</span>
        <span>{citation.chunk_id || t("citation.chunk")}</span>
      </p>
      <blockquote className="forge-citation-quote">“{citation.quote}”</blockquote>
    </article>
  );
}
