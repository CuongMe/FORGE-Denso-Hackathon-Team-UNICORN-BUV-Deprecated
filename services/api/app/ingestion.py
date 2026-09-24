from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from importlib.util import find_spec
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.visual import VisualDescription, VisualProviderError
from app.pipeline import StageCallback


DEFAULT_TOKENIZER = "local-whitespace"
DEFAULT_MAX_TOKENS = 384
SUPPORTED_INPUT_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".xlsx", ".csv"}
)


@dataclass(frozen=True, slots=True)
class IngestedProvenance:
    """The Docling region identity and coordinates attached to a chunk."""

    ref: str
    kind: str
    page: int | None
    bbox: tuple[float, float, float, float] | None
    coord_origin: str | None
    confidence: float | None = None
    review_required: bool = False


@dataclass(frozen=True, slots=True)
class ReviewCandidate:
    ref: str
    kind: str
    page: int | None
    bbox: tuple[float, float, float, float] | None
    confidence: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class IngestedChunk:
    """A normalized chunk record emitted by the optional Docling adapter."""

    chunk_index: int
    text: str
    page_numbers: tuple[int, ...]
    headings: tuple[str, ...]
    captions: tuple[str, ...]
    provenance: tuple[IngestedProvenance, ...] = ()
    review_candidates: tuple[ReviewCandidate, ...] = ()


def docling_available() -> bool:
    return find_spec("docling") is not None


def ingestion_status() -> dict[str, object]:
    """Expose the active ingestion boundary without importing optional ML packages."""
    available = docling_available()
    return {
        "backend": "docling-hybridchunker" if available else "unavailable",
        "docling_available": available,
        "chunker": "HybridChunker",
        "supported_extensions": sorted(SUPPORTED_INPUT_EXTENSIONS),
    }


def _page_numbers(chunk: object) -> tuple[int, ...]:
    meta = getattr(chunk, "meta", None)
    pages: set[int] = set()
    for item in getattr(meta, "doc_items", ()) or ():
        for provenance in getattr(item, "prov", ()) or ():
            page_no = getattr(provenance, "page_no", None)
            if isinstance(page_no, int):
                pages.add(page_no)
    return tuple(sorted(pages))


def _metadata_text(chunk: object, key: str) -> tuple[str, ...]:
    value = getattr(getattr(chunk, "meta", None), key, ()) or ()
    return tuple(str(item) for item in value)


def _enum_value(value: object) -> str | None:
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    return str(raw)


def _item_kind(item: object) -> str:
    item_type = type(item).__name__.casefold()
    label = _enum_value(getattr(item, "label", None)) or ""
    identity = f"{item_type} {label}".casefold()
    if "table" in identity:
        return "table"
    if "picture" in identity or "image" in identity or "figure" in identity:
        return "image"
    if "list" in identity:
        return "list"
    if "text" in identity or "header" in identity or "title" in identity:
        return "text"
    return "document"


def extract_chunk_provenance(chunk: object) -> tuple[IngestedProvenance, ...]:
    """Extract stable Docling item refs, page numbers, and layout coordinates."""
    meta = getattr(chunk, "meta", None)
    extracted: list[IngestedProvenance] = []
    for item in getattr(meta, "doc_items", ()) or ():
        ref = str(getattr(item, "self_ref", "") or "")
        if not ref:
            continue
        kind = _item_kind(item)
        provenances = getattr(item, "prov", ()) or ()
        if not provenances:
            extracted.append(
                IngestedProvenance(
                    ref=ref,
                    kind=kind,
                    page=None,
                    bbox=None,
                    coord_origin=None,
                )
            )
            continue
        for provenance in provenances:
            bbox = getattr(provenance, "bbox", None)
            coords = None
            if bbox is not None:
                values = tuple(
                    float(getattr(bbox, name))
                    for name in ("l", "t", "r", "b")
                    if getattr(bbox, name, None) is not None
                )
                if len(values) == 4:
                    coords = values  # type: ignore[assignment]
            page = getattr(provenance, "page_no", None)
            extracted.append(
                IngestedProvenance(
                    ref=ref,
                    kind=kind,
                    page=page if isinstance(page, int) else None,
                    bbox=coords,
                    coord_origin=_enum_value(getattr(bbox, "coord_origin", None)),
                )
            )
    return tuple(extracted)


def _item_provenance(item: object) -> tuple[IngestedProvenance, ...]:
    return extract_chunk_provenance(SimpleNamespace(meta=SimpleNamespace(doc_items=[item])))


def _fallback_records_for_orphaned_items(document: object) -> list[IngestedChunk]:
    """Recover OCR items that a converter did not attach to its body tree."""
    pictures = tuple(getattr(document, "pictures", ()) or ())
    records: list[IngestedChunk] = []
    for item in getattr(document, "texts", ()) or ():
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            continue
        item_provenance = _item_provenance(item)
        pages = tuple(
            sorted({item.page for item in item_provenance if item.page is not None})
        )
        records.append(
            IngestedChunk(
                chunk_index=len(records),
                text=text,
                page_numbers=pages,
                headings=(),
                captions=(),
                provenance=item_provenance,
            )
        )
    if records:
        return records
    for picture in pictures:
        provenance = _item_provenance(picture)
        pages = tuple(sorted({item.page for item in provenance if item.page is not None}))
        ref = provenance[0].ref if provenance else "image"
        records.append(
            IngestedChunk(
                chunk_index=len(records),
                text=f"Image region {ref}",
                page_numbers=pages,
                headings=(),
                captions=(),
                provenance=provenance,
            )
        )
    return records


def _build_local_tokenizer(max_tokens: int) -> object:
    """Build an offline tokenizer for deterministic local ingestion.

    Production deployments can set FORGE_CHUNK_TOKENIZER to a Hugging Face model
    so the chunk boundary counter matches the embedding tokenizer. The local
    fallback keeps the live demo independent of a model download while retaining
    HybridChunker's structure-aware behavior.
    """
    from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer

    class LocalWhitespaceTokenizer(BaseTokenizer):
        max_tokens: int

        def count_tokens(self, text: str) -> int:
            return len(re.findall(r"\S+", text))

        def get_max_tokens(self) -> int:
            return self.max_tokens

        def get_tokenizer(self):
            return lambda text: list(range(self.count_tokens(text)))

    return LocalWhitespaceTokenizer(max_tokens=max_tokens)


class DoclingHybridChunkerAdapter:
    """Convert supported files and emit contextualized, provenance-aware chunks.

    Docling's DocumentConverter handles source conversion, while its
    HybridChunker adds structure- and tokenizer-aware splitting. The default
    tokenizer is offline and deterministic; deployments can select the same
    Hugging Face tokenizer used by their embedding model.
    """

    def __init__(
        self,
        tokenizer_name: str | None = None,
        max_tokens: int | None = None,
        visual_describer: Any | None = None,
        review_threshold: float | None = None,
    ) -> None:
        self.tokenizer_name = tokenizer_name or os.getenv(
            "FORGE_CHUNK_TOKENIZER", DEFAULT_TOKENIZER
        )
        self.max_tokens = max_tokens
        self.visual_describer = visual_describer
        configured_threshold = review_threshold
        if configured_threshold is None:
            configured_threshold = float(os.getenv('FORGE_VLM_REVIEW_THRESHOLD', '0.75'))
        self.review_threshold = min(1.0, max(0.0, configured_threshold))
        self._converter: Any | None = None

    @staticmethod
    def _render_visual_region(document: object, region: IngestedProvenance) -> tuple[bytes, str] | None:
        if region.page is None or region.bbox is None:
            return None
        pages = getattr(document, 'pages', {}) or {}
        page = pages.get(region.page) if hasattr(pages, 'get') else None
        image_ref = getattr(page, 'image', None)
        page_size = getattr(page, 'size', None)
        if image_ref is None or page_size is None:
            return None
        try:
            image = image_ref.pil_image
            if image is None:
                return None
            page_width = float(getattr(page_size, 'width', 0.0))
            page_height = float(getattr(page_size, 'height', 0.0))
            if page_width <= 0 or page_height <= 0:
                return None
            left, top, right, bottom = region.bbox
            if (region.coord_origin or '').casefold() == 'bottomleft':
                top, bottom = page_height - bottom, page_height - top
            scale_x = image.width / page_width
            scale_y = image.height / page_height
            bounds = (
                max(0, min(image.width, round(left * scale_x))),
                max(0, min(image.height, round(top * scale_y))),
                max(0, min(image.width, round(right * scale_x))),
                max(0, min(image.height, round(bottom * scale_y))),
            )
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                return None
            cropped = image.convert('RGB').crop(bounds)
            output = BytesIO()
            cropped.save(output, format='PNG', optimize=True)
            return output.getvalue(), 'image/png'
        except Exception:
            return None

    def _enrich_visual_records(
        self,
        source: Path,
        records: list[IngestedChunk],
        document: object | None = None,
        progress_callback: StageCallback | None = None,
    ) -> list[IngestedChunk]:
        visual_total = sum(
            1 for record in records for item in record.provenance if item.kind == 'image'
        )
        if progress_callback:
            progress_callback('vlm_analysis', 'started', 0, 'Preparing visual regions for Gemini analysis.')
        if not visual_total:
            if progress_callback:
                progress_callback('vlm_analysis', 'completed', 100, 'No visual regions detected; VLM analysis was not required.')
            return records

        enriched: list[IngestedChunk] = []
        processed = 0
        failures = 0
        for record in records:
            visual_regions = [item for item in record.provenance if item.kind == 'image']
            if not visual_regions:
                enriched.append(record)
                continue
            descriptions: list[str] = []
            reviews: list[ReviewCandidate] = []
            provenance = list(record.provenance)
            for region in visual_regions:
                if self.visual_describer is None:
                    failures += 1
                    reviews.append(
                        ReviewCandidate(
                            ref=region.ref,
                            kind=region.kind,
                            page=region.page,
                            bbox=region.bbox,
                            confidence=None,
                            reason='VLM adapter is not configured.',
                        )
                    )
                    processed += 1
                    continue
                try:
                    rendered = self._render_visual_region(document, region)
                    if rendered and hasattr(self.visual_describer, 'describe_region'):
                        data, mime_type = rendered
                        result: VisualDescription = self.visual_describer.describe_region(
                            data,
                            mime_type=mime_type,
                            region_ref=region.ref,
                            page=region.page,
                        )
                    else:
                        result = self.visual_describer.describe(
                            source,
                            region_ref=region.ref,
                            page=region.page,
                        )
                except VisualProviderError:
                    failures += 1
                    reviews.append(
                        ReviewCandidate(
                            ref=region.ref,
                            kind=region.kind,
                            page=region.page,
                            bbox=region.bbox,
                            confidence=0.0,
                            reason='VLM processing failed; human review is required.',
                        )
                    )
                    processed += 1
                    continue
                descriptions.append(result.description)
                needs_review = result.review_required or result.confidence < self.review_threshold
                index = provenance.index(region)
                provenance[index] = replace(region, confidence=result.confidence, review_required=needs_review)
                if needs_review:
                    reviews.append(
                        ReviewCandidate(
                            ref=region.ref,
                            kind=region.kind,
                            page=region.page,
                            bbox=region.bbox,
                            confidence=result.confidence,
                            reason=result.reason or 'Visual confidence is below the review threshold.',
                        )
                    )
                processed += 1
                if progress_callback:
                    progress_callback('vlm_analysis', 'started', round(processed / visual_total * 100), f'Analyzed visual region {processed} of {visual_total}.')
            text = record.text
            for description in descriptions:
                if description and description not in text:
                    text = f'{text}\n\nVisual description: {description}'.strip()
            enriched.append(replace(record, text=text, provenance=tuple(provenance), review_candidates=tuple(reviews)))

        if progress_callback:
            if failures == visual_total:
                progress_callback('vlm_analysis', 'failed', 100, 'Gemini could not analyze the visual regions; human review is required.')
            else:
                review_count = sum(len(record.review_candidates) for record in enriched)
                message = f'Analyzed {visual_total} visual region(s); {review_count} sent to review.' if review_count else f'Analyzed {visual_total} visual region(s).'
                progress_callback('vlm_analysis', 'completed', 100, message)
        return enriched

    def _max_tokens(self) -> int:
        configured = self.max_tokens
        if configured is None:
            configured = int(os.getenv("FORGE_CHUNK_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        if configured < 32:
            raise ValueError("Chunk token limit must be at least 32 tokens.")
        return configured

    @property
    def cache_key(self) -> str:
        return f"{self.tokenizer_name}:{self._max_tokens()}"

    def _tokenizer(self) -> object:
        max_tokens = self._max_tokens()
        if self.tokenizer_name.casefold() in {"local", "local-whitespace"}:
            return _build_local_tokenizer(max_tokens)

        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer

        return HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(self.tokenizer_name),
            max_tokens=max_tokens,
        )

    def _document_converter(self) -> Any:
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    def convert_and_chunk(
        self,
        source: Path,
        *,
        progress_callback: StageCallback | None = None,
    ) -> list[IngestedChunk]:
        if source.suffix.casefold() not in SUPPORTED_INPUT_EXTENSIONS:
            raise ValueError(f"Unsupported ingestion format: {source.suffix}")
        if not source.is_file():
            raise FileNotFoundError(source)
        if not docling_available():
            raise RuntimeError(
                "The optional Docling ingestion extra is not installed. "
                "Install it with: uv pip install -r requirements-docling.txt"
            )

        from docling.chunking import HybridChunker

        if progress_callback:
            progress_callback('parsing', 'started', 0, 'Detecting document layout with Docling.')
        document = self._document_converter().convert(source=source).document
        if progress_callback:
            progress_callback('parsing', 'completed', 100, 'Docling layout detection completed.')
            progress_callback('ocr', 'started', 0, 'Checking scanned regions with Docling OCR.')
            progress_callback('ocr', 'completed', 100, 'Docling OCR pass completed where scanned text was present.')
            progress_callback('table_extraction', 'started', 0, 'Extracting tables with Docling TableFormer.')
            progress_callback('table_extraction', 'completed', 100, 'Docling table extraction completed.')
        tokenizer = self._tokenizer()
        chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

        if progress_callback:
            progress_callback('chunking', 'started', 0, 'Building context-preserving HybridChunker chunks.')
        records: list[IngestedChunk] = []
        for index, chunk in enumerate(chunker.chunk(dl_doc=document)):
            records.append(
                IngestedChunk(
                    chunk_index=index,
                    text=chunker.contextualize(chunk=chunk),
                    page_numbers=_page_numbers(chunk),
                    headings=_metadata_text(chunk, "headings"),
                    captions=_metadata_text(chunk, "captions"),
                    provenance=extract_chunk_provenance(chunk),
                )
            )
        if not records:
            records = _fallback_records_for_orphaned_items(document)
        if progress_callback:
            progress_callback('chunking', 'completed', 100, f'Created {len(records)} context-preserving chunk(s).')
        return self._enrich_visual_records(source, records, document, progress_callback)
