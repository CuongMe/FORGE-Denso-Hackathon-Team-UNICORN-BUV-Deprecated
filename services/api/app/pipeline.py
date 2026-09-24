from __future__ import annotations

from collections.abc import Callable
from typing import Literal


StageStatus = Literal['pending', 'started', 'completed', 'failed']
StageCallback = Callable[[str, StageStatus, int, str], None]


INGESTION_STAGE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ('queued', 'Queued'),
    ('uploading', 'Uploading'),
    ('parsing', 'Parsing'),
    ('ocr', 'OCR'),
    ('table_extraction', 'Table Extraction'),
    ('vlm_analysis', 'VLM Analysis'),
    ('chunking', 'Chunking'),
    ('embedding', 'Embedding'),
    ('indexing', 'Indexing'),
    ('completed', 'Completed'),
)

INGESTION_STAGE_LABELS = dict(INGESTION_STAGE_DEFINITIONS)
