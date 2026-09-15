# Factory AI Agent - Data Preparation Starter Pack

> **AI-GENERATED SUPPLY PACK:** This entire starter pack is synthetic content generated for AI demonstration, testing, and evaluation. It must not be presented as an official factory document or operational record.

This package is a **synthetic, non-confidential dataset** for the hackathon challenge: **AI Agent Understanding Diverse Document Formats**. It is designed to mimic common factory information without using any official DENSO document, logo, customer data, employee data, or proprietary production specification.

## What is included

- **8 PDFs**: work instruction, bilingual defect SOP, preventive-maintenance checklist, bilingual LOTO alert, NCR, shift handover, supplier packing list, and Andon summary.
- **4 raster images**: rotated/noisy startup check sheet, machine HMI alarm screen, traceability/pallet label, and bilingual forklift-safety poster.
- **5 table files**: production log, quality inspection results, maintenance history, bilingual EN-VI term dictionary, and defect catalog CSV.
- **Ground truth**: RAG question-answer pairs and expected field-extraction values.
- **Dataset catalog**: metadata and suggested benchmark coverage.

## Folder structure

```text
pdfs/          Native PDFs with text, tables, English, and Vietnamese-English content
images/        OCR / vision-style inputs with rotation, noise, UI text, and labels
tables/        XLSX and CSV data for structured/table understanding
ground_truth/  Evaluation Q&A and expected extracted fields
```

## Recommended hackathon tests

1. **Native PDF extraction** - retrieve procedures, IDs, dates, limits, quantities, and actions.
2. **OCR robustness** - handle rotation, light scan noise, dense labels, and screen text.
3. **Table understanding** - answer questions from XLSX/CSV and preserve row/column relationships.
4. **Bilingual retrieval** - ask in Vietnamese and answer from Vietnamese-English documents; test cross-language embeddings.
5. **Numeric accuracy** - protect units and limits such as `9.5 ± 0.5 N·m`, `0.50-0.60 MPa`, and `1.80-1.90 mm`.
6. **Cross-document reasoning** - connect the shift handover, NCR, maintenance record, Andon event, and inspection table around the same synthetic line/lot.
7. **Metadata extraction** - document ID, revision, lot, part number, machine ID, date, shift, status, and severity.
8. **Latency benchmark** - compare ingestion time, chunking/index time, and first-token/complete-answer response time by modality.

## Suggested RAG evaluation protocol

- Ingest every file in `pdfs/`, `images/`, and `tables/`.
- Preserve source filename and document ID as metadata.
- Use OCR/VLM only when needed; use native parsers for text PDFs and spreadsheets where possible.
- Run every entry in `ground_truth/rag_eval_qa.jsonl`.
- Record: exact/semantic correctness, citation/source accuracy, response latency, and failure type.
- For numeric answers, treat unit or decimal mistakes as incorrect.

## Important note

All names, part numbers, lots, measurements, events, contacts, and operational details in this pack are fabricated for AI testing. This pack should not be treated as an operational factory standard.
