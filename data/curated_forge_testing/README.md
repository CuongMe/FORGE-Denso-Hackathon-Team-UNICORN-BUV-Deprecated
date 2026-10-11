# FORGE testing dataset

This folder is the small, repeatable test pack for FORGE functionality checks. It is intentionally separate from the AI-generated demo data and from the evaluation prompts.

## Layout

- `images/ja_business_doc_rq_bench/` — 30 Japanese chart, table, diagram, and document images, licensed under Apache-2.0 by the source dataset.
- `ground_truth/ja_business_doc_rq_bench_metadata.jsonl` — source questions and expected answers for those images.
- `tabular/industrial_dataset.csv` — project fixture for ingestion and query tests.
- `images/vixio_metal_nut/`, `ground_truth/vixio_metal_nut/`, and `tabular/Intelligent_Production_IIoT.csv` — local-only files; not included in Git while redistribution terms remain unverified.
- `ground_truth/` — source metadata for the selected JA benchmark images.

The JA benchmark provides image-level question/answer ground truth. Local VIXIO samples include paired defect masks for three defect classes; those files stay out of the public repository until redistribution terms are confirmed.

## Redistribution and licensing

Source records preserve provenance and known licensing status. The Apache-2.0 JA benchmark files are included with attribution. VIXIO images and masks, plus the Kaggle CSV, stay local until their redistribution terms are confirmed.
