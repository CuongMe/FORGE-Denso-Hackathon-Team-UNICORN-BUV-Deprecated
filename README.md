<p align="center">
  <img src="./apps/web/public/forge-mark.svg" alt="FORGE Factory Operations Retrieval &amp; Generation Engine logo" width="120" height="120" />
</p>

<h1 align="center">FORGE: Factory Operations Retrieval &amp; Generation Engine</h1>

<p align="center">
  <strong>Multimodal factory document intelligence for grounded, traceable answers.</strong><br />
  Denso Factory Hackathon 2026 · Challenge A3
</p>

FORGE is a multi-format document understanding and retrieval-augmented generation (RAG) system. It is designed to process PDFs, images, tables, and bilingual documents using OCR/VLM, layout-aware extraction, multilingual embeddings, and vector search - enabling accurate chatbot responses without manual preprocessing.

## Pain point

Factory operations knowledge is often spread across PDFs, scanned images, tables, and bilingual documents. Each format can require different preprocessing, including OCR, layout reconstruction, table extraction, and language handling, before an AI system can search and use the content. When that work is manual or inconsistent, valuable information takes longer to access and chatbot answers can miss or misread important context. This makes it difficult to build one dependable retrieval workflow for the documents teams already use.

## Unique selling point

FORGE is built around an evidence contract: document structure and provenance stay attached from page and region through chunk, retrieval, reranking, and citation. This lets one auditable pipeline handle text, tables, visuals, and bilingual evidence while measuring not only answer quality, but also whether the system should abstain. Its retrieval boundary is designed to support learned evidence-path routing without replacing the core pipeline.

## Data Curation

Input data validates FORGE across document, visual, and tabular ingestion paths. The project keeps AI-generated functionality data separate from the external testing dataset.

| Data source | Description and sources |
|---|---|
| **AI-generated functionality data** | Synthetic factory PDFs, scans, images, spreadsheets, and CSVs created for functionality testing. It exercises ingestion, OCR, visual analysis, retrieval, and UI flows. Source: [`data/denso_factory_hack_data_prep`](data/denso_factory_hack_data_prep). |
| **Curated FORGE testing data** | External test pack containing 30 [JA-Business-Doc-RQ-Bench](https://huggingface.co/datasets/stockmark/JA-Business-Doc-RQ-Bench) images with Q&A ground truth, 30 [Mitsubishi Electric VIXIO](https://www.mitsubishielectric.com/fa/download/software/detailsearch.page?mode=lib&kisyu=/vixio&shiryoid=1000000933&lang=2&select=0&softid=3&infostatus=2_2_2&viewradio=0&viewstatus=&viewpos=) metal-nut images with 18 paired defect masks, and [`Intelligent_Production_IIoT.csv`](https://www.kaggle.com/datasets/colabsss/intelligent-production-operations-dataset) plus [`industrial_dataset.csv`](data/legacy_industrial_equipment_sensor_logs/industrial_dataset.csv). Sources and counts: [`dataset_manifest.json`](data/curated_forge_testing/dataset_manifest.json); review checklist: [`golden_data_checklist.xlsx`](data/curated_forge_testing/golden_data_checklist.xlsx). |

### Curation Principles

- **Source-linked:** Provider, download link, selection, and provenance are recorded in the manifest.
- **Safe to test:** AI-generated data is synthetic; external samples contain no project-specific confidential material.
- **Reproducible:** Curated files, counts, ground truth, and review status are versioned with the project.
- **Metadata-complete:** Each source records its modality, intended test path, and available ground truth.

## Solution architecture

FORGE uses a multimodal retrieval-augmented generation pipeline. The indexing path converts mixed-format documents into searchable, context-preserving representations. The answering path combines a user's question with the most relevant content and passes both to an LLM for a grounded response.

```mermaid
%%{init: {'themeVariables': {'fontSize': '16px', 'fontFamily': 'Trebuchet MS, Verdana, Arial, sans-serif'}, 'flowchart': {'nodeSpacing': 50, 'rankSpacing': 70}}}%%
flowchart TB
    USER(["👤 Factory Engineer"])
    UI["Next.js chat + upload UI"]
    API["FastAPI API"]

    USER -->|asks question| UI
    UI -->|upload / query| API

    subgraph INGESTION["📥 Ingestion Pipeline (per document)"]
        PARSE["Docling + OCR<br/>TableFormer + VLM"]
        CHUNK["HybridChunker<br/>context + provenance"]
        EMBED["BGE-M3<br/>(dense + sparse)"]
        PARSE -->|structured blocks| CHUNK
        CHUNK -->|text chunks| EMBED
    end

    subgraph QUERY["💬 Query Pipeline (per question)"]
        RETRIEVE["Hybrid retrieval"]
        RERANK["Cross-encoder reranking"]
        GEMINI["Gemini grounded generation<br/>(query + retrieved context)"]
        CHECK{"Evidence sufficient?"}
        ANSWER["Cited answer"]
        ABSTAIN["Abstention: 'I don't know'"]

        RETRIEVE --> RERANK --> GEMINI --> CHECK
        CHECK -->|yes| ANSWER
        CHECK -->|no| ABSTAIN
    end

    API --> PARSE
    API --> RETRIEVE

    EMBED -->|vectors| QDRANT[("Qdrant vector store")]
    CHUNK -->|metadata| SQLITE[("SQLite metadata")]
    PARSE -->|files & images| FILES[("Local FileSystem")]

    QDRANT -->|top-K candidates| RETRIEVE
    ANSWER --> UI

    classDef node fill:#E8F0FE,stroke:#2563EB,color:#333333
    class USER,UI,API,PARSE,CHUNK,EMBED,RETRIEVE,RERANK,GEMINI,CHECK,ANSWER,ABSTAIN,QDRANT,SQLITE,FILES node
    style INGESTION fill:#EFF6FF,stroke:#1D4ED8,color:#333333
    style QUERY fill:#EFF6FF,stroke:#1D4ED8,color:#333333
    linkStyle default stroke:#333333,stroke-width:1px
```

### Design principles

- **Layout-aware:** document structure is treated as part of the meaning, especially for tables, forms, and multi-column pages.
- **Multimodal:** the pipeline handles information found in text, images, and visual document elements.
- **Language-aware:** multilingual processing and embeddings support bilingual operational content.
- **Context-preserving:** tokenizer-aware chunking keeps related content together so retrieval does not lose the relationships created by the original layout.
- **Traceable:** each chunk retains source metadata so generated answers can be checked against the original document.

## Target deliverables

- Multi-format document ingestion pipeline
- RAG chatbot demonstration
- Retrieval, answer quality, and latency report
- Evaluation dashboard comparing a naive baseline with FORGE

## Technology stack

FORGE runs as native Python and Node.js processes or on managed services; Docker is optional.

| Layer | Technology | Purpose | Icon |
|---|---|---|:---:|
| Frontend | [Next.js](https://nextjs.org/docs/app) · React · TypeScript · Tailwind CSS | Chat UI and uploads | <img src='https://cdn.simpleicons.org/nextdotjs/000000' alt='Next.js' title='Next.js' height='20' /> <img src='https://cdn.simpleicons.org/react/61DAFB' alt='React' title='React' height='20' /> <img src='https://cdn.simpleicons.org/typescript/3178C6' alt='TypeScript' title='TypeScript' height='20' /> <img src='https://cdn.simpleicons.org/tailwindcss/06B6D4' alt='Tailwind CSS' title='Tailwind CSS' height='20' /> |
| API | Python · [FastAPI](https://fastapi.tiangolo.com/) · Pydantic | Typed document and query contracts | <img src='https://cdn.simpleicons.org/python/3776AB' alt='Python' title='Python' height='20' /> <img src='https://cdn.simpleicons.org/fastapi/009688' alt='FastAPI' title='FastAPI' height='20' /> <img src='https://cdn.simpleicons.org/pydantic/E92063' alt='Pydantic' title='Pydantic' height='20' /> |
| Ingestion | [Docling](https://docling.org/) · OCR · `HybridChunker` | Layout-aware parsing and chunking | <img src='https://github.com/docling-project.png?size=64' alt='Docling' title='Docling' height='20' /> |
| Visual understanding | [Florence-2](https://huggingface.co/microsoft/Florence-2-base-ft) · Gemini (optional) | Local visual captions; Gemini fallback | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Florence-2 on Hugging Face' height='20' /> <img src='https://cdn.simpleicons.org/googlegemini/8E75B2' alt='Gemini' title='Gemini' height='20' /> |
| Embeddings | [BGE-M3](https://bge-model.com/bge/bge_m3.html) | Multilingual vector representations | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Retrieval | [Qdrant](https://qdrant.tech/documentation/search/text-search/hybrid-search/) (self-hosted) | Dense/sparse hybrid search and fusion | <img src='https://cdn.simpleicons.org/qdrant/DC244C' alt='Qdrant' title='Qdrant' height='20' /> |
| Reranking | [`bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) · CrossEncoder | Candidate reranking | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Metadata | SQLite · PostgreSQL-ready | Documents, status, evaluation, and audit data | <img src='https://cdn.simpleicons.org/sqlite/003B57' alt='SQLite' title='SQLite' height='20' /> |
| Storage | Local filesystem | Uploads and processed artifacts | — |
| Jobs | Python worker | Background ingestion and re-indexing | <img src='https://cdn.simpleicons.org/python/3776AB' alt='Python' title='Python' height='20' /> |
| Generation | Gemini 2.5 Flash-Lite (free tier for demo) · `google-genai` | Grounded answer generation | <img src='https://cdn.simpleicons.org/googlegemini/8E75B2' alt='Gemini' title='Gemini' height='20' /> |
| Tooling | `uv` · `pnpm` | Python and Node.js dependencies | <img src='https://cdn.simpleicons.org/uv/6E56CF' alt='uv' title='uv' height='20' /> <img src='https://cdn.simpleicons.org/pnpm/F69220' alt='pnpm' title='pnpm' height='20' /> |

## Evaluation framework

A reliable RAG system needs to be evaluated at every important boundary, from document extraction to the final answer. FORGE uses golden data prompts, a consistent metric set, and repeatable evaluation tooling.

### 1. The golden dataset

Golden data prompts are human-authored evaluation inputs. Each prompt includes a question and expected answer; the expected answer is the ground truth used to evaluate retrieval, generation, correctness, and abstention. Use the human-review checklist in [`data/curated_forge_testing/golden_data_checklist.xlsx`](data/curated_forge_testing/golden_data_checklist.xlsx); JSONL remains only as a machine-readable runtime fixture where required.

### 2. The metrics

| **Metric** | **What it measures** | **Implementation** |
|---|---|---|
| **Hit@5** | Retrieval finds the right evidence | Python |
| **Context Recall** | Retrieval finds all needed evidence | Ragas |
| **Faithfulness** | LLM does not hallucinate | Ragas |
| **Answer Correctness** | Answers match ground truth | Ragas |
| **Answerability F1** | System abstains when it should | Python |
| **p95 Latency** | System is fast enough for production | Python |
| **Validation** | Regression checks and human calibration | Python |

Each run records the corpus, parser, chunker, embedding model, reranker, LLM, prompt, retrieval settings, and timestamp.

#### Cost accounting

These are demo estimates; production reporting should use the model, token, image, and infrastructure usage recorded for each run.

##### 1. Cost per query

| Assumption | Estimate |
|---|---:|
| Average input tokens (question + five chunks) | ~2,000 |
| Average output tokens | ~200 |
| Gemini Flash-Lite input price | $0.075 / 1M tokens |
| Gemini Flash-Lite output price | $0.30 / 1M tokens |

**Estimated cost per query** = `(2,000 × $0.075 + 200 × $0.30) / 1,000,000` = **$0.00021** (approximately **$0.0002**).

##### 2. Cost per document

When Docling, BGE-M3, Qdrant, Florence-2, and local storage run locally, ingestion and visual analysis are approximately **$0.00 per document** aside from self-hosted compute. Gemini remains an optional visual fallback; its usage is provider-priced.

##### 3. Monthly demo TCO

| Component | Monthly estimate |
|---|---:|
| Oracle Cloud VPS (Always Free) | $0 |
| Gemini API (10,000 queries) | $2.10 |
| Florence-2 visual analysis (local) | $0 |
| Self-hosted services and local storage | $0 |
| **Estimated total** | **$2.10/month** |

The total excludes paid VLM overages, evaluation calls, and future managed-service costs.

### License

This project is licensed under the [Apache License 2.0](LICENSE).

### Baseline comparison

Run both systems on the same corpus and golden dataset:

- **Naive baseline:** fixed-size chunking, dense-only retrieval, no cross-encoder reranking, and the same generation model where possible.
- **FORGE:** Docling `HybridChunker`, hybrid dense and sparse retrieval, cross-encoder reranking, and the same generation model.

The results dashboard should show measured values and the change from baseline. Until the experiment is run, use `TBD` rather than presenting sample numbers as results.

| Category | Metric | Naive baseline | FORGE | Change |
|---|---|---:|---:|---:|
| Retrieval | Context recall | TBD | TBD | TBD |
| Retrieval | Reranker lift, MRR | N/A | TBD | TBD |
| Generation | Faithfulness | TBD | TBD | TBD |
| Generation | Answerability F1 | TBD | TBD | TBD |
| Operations | p95 latency | TBD | TBD | TBD |
| Operations | Cost per query | TBD | TBD | TBD |
