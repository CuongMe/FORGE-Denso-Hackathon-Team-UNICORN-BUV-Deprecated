# FORGE curated test data

This folder contains two external datasets used for repeatable ingestion and multimodal retrieval tests. The AI-generated factory pack and golden evaluation questions are maintained separately.

## Included datasets

- **JA-Business-Doc-RQ-Bench:** 30 selected Japanese chart, table, diagram, and document images, with source questions and answers in `ground_truth/ja_business_doc_rq_bench_metadata.jsonl`. [Source dataset](https://huggingface.co/datasets/stockmark/JA-Business-Doc-RQ-Bench), licensed under Apache-2.0.
- **Screw Dataset:** 30 images and 30 paired segmentation masks, with five samples from each of six classes. Images are under `images/screw_dataset/`; masks and annotations are under `ground_truth/screw_dataset/`. [Source dataset](https://huggingface.co/datasets/shrish23/screw-dataset), licensed CC BY 4.0; attribution to shrish23 is required.

VIXIO was dropped because its samples are not licensed for open distribution.
