# FORGE Golden Evaluation Dataset

[`golden_dataset_v2_en.jsonl`](golden_dataset_v2_en.jsonl) is the active machine-readable set: 34 new English questions covering all 17 files in the current source pack. Its human-review checklist is [`golden_dataset_v2_en.md`](golden_dataset_v2_en.md), and the combined English/Japanese review export is [`golden_dataset_v2_en_ja.csv`](golden_dataset_v2_en_ja.csv). [`golden_dataset_v1.jsonl`](golden_dataset_v1.jsonl) remains available as the archived 30-case set.

Each case pairs a question with a reference answer and source evidence. The reference answer is the ground truth used for evaluation:

- 34 answerable English cases covering native PDFs, bilingual PDFs, image OCR, image layout, XLSX, CSV, SQL-style aggregation, numeric values, procedures, and event lookups.
- Negative abstention cases are intentionally kept out of this answerable-only release; they are preserved in [`abstention_holdout_v1.jsonl`](abstention_holdout_v1.jsonl) for the Honest Demo and safety evaluation.

## Disclosure and verification status

The source pack is synthetic and AI-generated for demonstration and evaluation. It is not an official factory standard or operational record.

Every case in this file has been source-verified against the supplied PDF, image, XLSX, or CSV evidence. The field `verification_status` intentionally ends in `pending_human_signoff`: an AI-assisted source check is not the same thing as a human review. Before presenting scores as ground truth, a reviewer must complete [`human_review_log.csv`](human_review_log.csv) and update the case records after review.

## Record contract

Each JSONL record contains:

- `case_id`: stable evaluation identifier.
- `question`, `language`, and `question_type`: the test input and coverage label.
- `answerable`: whether the corpus contains sufficient evidence.
- `reference_answer`: expected answer for the answerable case.
- `required_facts`: atomic facts needed for a correct answer.
- `gold_evidence`: one or more source locators with an exact evidence quote.
- `chunk_id`: the current deterministic demo chunk ID for the original 23 cases, or a stable source-row anchor for tabular evidence. Production Docling chunk IDs may differ, so evaluators should also match `doc_id`, source path, page/region, and quote.
- `verification_status` and `verification_note`: provenance and review state.

## Human sign-off protocol

For each case, the reviewer should:

1. Open every `gold_evidence.source_path` and confirm the quote, page/region, and field or row.
2. Check that `reference_answer` preserves every required number, unit, condition, language, and entity.
3. Confirm that each case is answerable and that its gold evidence is sufficient to support the reference answer.
4. Check that the expected evidence is sufficient without relying on unstated operational knowledge.
5. Record reviewer name, date, decision, and notes. Reject or edit any case that fails one of these checks.

The set is ready for scoring only when every case has a human decision of `accepted`. If any accepted case is changed, rerun the affected evaluation slice and increment the dataset version.

## Recommended split

Use the full set for regression testing. For a quick demo benchmark, report these slices separately:

- Retrieval and procedures: G101-G116.
- Visual/OCR: G117-G124.
- Tables and CSV: G125-G134.
- Archived v1 cases: [`golden_dataset_v1.md`](golden_dataset_v1.md).
- Negative holdout: [`abstention_holdout_v1.jsonl`](abstention_holdout_v1.jsonl), kept separate from this answerable-only dataset.

Do not publish invented accuracy numbers. Record the dataset version, model versions, prompt version, retrieval settings, and run timestamp with every evaluation result.
