from __future__ import annotations

from app.models import Citation, RetrievedChunk


ABSTENTION_TEXT = (
    "I don't know based on the indexed documents. "
    "I could not find sufficient evidence to answer that question."
)


class AnswerDraft:
    def __init__(self, answer: str, abstained: bool, citations: list[Citation]) -> None:
        self.answer = answer
        self.abstained = abstained
        self.citations = citations


class GroundedAnswerer:
    def __init__(self, evidence_threshold: float = 0.34) -> None:
        self.evidence_threshold = evidence_threshold

    def answer(self, question: str, results: list[RetrievedChunk]) -> AnswerDraft:
        if not results:
            return self._abstention()

        best = results[0]
        score = best.rerank_score if best.rerank_score is not None else best.hybrid_score
        if score < self.evidence_threshold:
            return self._abstention()

        citation = Citation(
            chunk_id=best.chunk.chunk_id,
            doc_id=best.chunk.doc_id,
            source_name=best.chunk.source_name,
            source_path=best.chunk.source_path,
            page=best.chunk.page,
            pages=best.chunk.pages,
            region=best.chunk.region,
            region_type=best.chunk.region_type,
            provenance=best.chunk.provenance,
            quote=best.chunk.content,
            score=score,
        )
        return AnswerDraft(
            answer=best.chunk.content,
            abstained=False,
            citations=[citation],
        )

    @staticmethod
    def _abstention() -> AnswerDraft:
        return AnswerDraft(
            answer=ABSTENTION_TEXT,
            abstained=True,
            citations=[],
        )
