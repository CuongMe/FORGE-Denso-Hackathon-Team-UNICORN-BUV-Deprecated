# FORGE Golden Evaluation Dataset

`golden_dataset_v1.jsonl` is the first structured evaluation set for FORGE. It contains 30 answerable cases:

- 30 answerable cases covering native PDFs, bilingual PDFs, image OCR, image layout, XLSX, CSV, numeric precision, procedures, ranking, aggregation, and cross-document reasoning.
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

- Retrieval: G001-G007, G009-G013, G015-G016, and G018-G034.
- Visual/OCR: G020-G023.
- Tables: G024-G030 and G032-G034.
- Bilingual: G004, G006, G009, G023, and G030.
- Negative holdout: [`abstention_holdout_v1.jsonl`](abstention_holdout_v1.jsonl), kept separate from this answerable-only dataset.

Do not publish invented accuracy numbers. Record the dataset version, model versions, prompt version, retrieval settings, and run timestamp with every evaluation result.
