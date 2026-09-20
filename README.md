<p align="center">
  <img src="./apps/web/public/forge-mark.svg" alt="FORGE Factory Operations Retrieval &amp; Generation Engine logo" width="120" height="120" />
</p>

<h1 align="center">FORGE Factory Operations Retrieval &amp; Generation Engine</h1>

<p align="center">
  <strong>Multimodal factory document intelligence for grounded, traceable answers.</strong><br />
  Denso Factory Hackathon 2026 · Challenge A3
</p>

> **Dataset disclosure:** The supplied factory data-preparation/supply pack is **AI-generated synthetic data** for demonstration and evaluation only. It contains no official factory standard, confidential information, or production record.

FORGE is a multi-format document understanding and retrieval-augmented generation (RAG) system. It is designed to process PDFs, images, tables, and bilingual documents using OCR/VLM, layout-aware extraction, multilingual embeddings, and vector search - enabling accurate chatbot responses without manual preprocessing.

## Pain point

Factory operations knowledge is often spread across PDFs, scanned images, tables, and bilingual documents. Each format can require different preprocessing, including OCR, layout reconstruction, table extraction, and language handling, before an AI system can search and use the content. When that work is manual or inconsistent, valuable information takes longer to access and chatbot answers can miss or misread important context. This makes it difficult to build one dependable retrieval workflow for the documents teams already use.

## Unique selling point

FORGE is built around an evidence contract: document structure and provenance stay attached from page and region through chunk, retrieval, reranking, and citation. This lets one auditable pipeline handle text, tables, visuals, and bilingual evidence while measuring not only answer quality, but also whether the system should abstain. Its retrieval boundary is designed to support learned evidence-path routing without replacing the core pipeline.

## Data Curation

Input data is the foundation for validating the RAG system. To test every capability of the pipeline, the input corpus is curated from a diverse collection of open-source datasets, all licensed under permissive terms (Creative Commons, CC0, MIT, Apache 2.0, or public domain).

### Format Coverage

The corpus exercises every claimed input path through two linked sets:

**Coverage links**

- **Digital PDF** → Docling text extraction and reading order
- **Scanned PDF** → OCR and noisy-layout detection
- **PDF with complex tables** → TableFormer and table-aware chunking
- **PDF with charts or diagrams** → VLM adapter and image-block extraction
- **Bilingual PDF (VN/JP, VN/EN)** → BGE-M3 cross-lingual retrieval
- **Excel / CSV / XLSX** → structured parsing and row/column chunking
- **Standalone images** → VLM description and image understanding
- **Mixed PDF (text + table + image)** → structure parsing and multi-block handling

### Difficulty Tiers

Documents are stratified into six tiers for difficulty-specific reporting:

- **Tier 1 — Clean:** Digital PDF, single language, simple layout
- **Tier 2 — Structured:** Tables, headings, lists, nested sections
- **Tier 3 — Visual:** Charts, diagrams, embedded images
- **Tier 4 — Degraded:** Scanned, blurry, rotated, or low-resolution input
- **Tier 5 — Multilingual:** Bilingual or cross-lingual content
- **Tier 6 — Adversarial:** Missing pages, contradictory information, out-of-domain content

At least 60% of the corpus is Tier 2–5, ensuring FORGE is tested on realistic industrial complexity rather than only clean documents.

### Curation Principles

- **Open and licensed**: All documents are open-source or public domain, with clear attribution.
- **No PII or confidential content**: No personally identifiable information or proprietary Denso material.
- **Versioned and reproducible**: The corpus is tagged (e.g., `corpus_v1.0`) and referenced in every evaluation report.
- **Metadata-complete**: Each document carries a manifest record (format, tier, language, page count, source, license).
- **Bounded**: 10–20 documents, 80–200 pages total, enough for meaningful evaluation without exceeding 15 minutes per run.

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

### Pipeline stages

#### Ingestion

```mermaid
%%{init: {'themeVariables': {'fontSize': '15px'}, 'flowchart': {'curve': 'linear', 'nodeSpacing': 30, 'rankSpacing': 40}}}%%
flowchart TB
    INPUT["📄 PDFs • images • CSV • XLSX"]
    RECORD["Record document + metadata"]
    LAYOUT["Docling layout detection<br/>text • tables • figures • images"]
    VISUAL["OCR + VLM<br/>extract text + describe visuals"]
    CONVERT["Semantic conversion<br/>Markdown / JSON preserved"]
    CHUNK["HybridChunker<br/>context-aware + tokenizer-aware"]
    EMBED["BGE-M3<br/>multilingual embeddings"]

    QDRANT[("Qdrant<br/>vector index")]
    SQLITE[("SQLite<br/>document + chunk metadata")]
    FILES[("Local FileSystem<br/>originals + page images")]

    INPUT --> RECORD
    RECORD --> LAYOUT
    LAYOUT --> VISUAL
    VISUAL --> CONVERT
    CONVERT --> CHUNK
    CHUNK --> EMBED
    EMBED --> QDRANT

    RECORD -.-> SQLITE
    RECORD -.-> FILES
    VISUAL -.-> FILES
    CHUNK -.-> SQLITE

    classDef process fill:#D1FAE5,stroke:#047857,color:#064E3B,stroke-width:1.5px
    classDef store fill:#FEF3C7,stroke:#B45309,color:#78350F,stroke-width:1.5px
    classDef input fill:#DBEAFE,stroke:#1E40AF,color:#1E3A8A,stroke-width:1.5px

    class INPUT input
    class RECORD,LAYOUT,VISUAL,CONVERT,CHUNK,EMBED process
    class QDRANT,SQLITE,FILES store
```

#### Query

```mermaid
%%{init: {'themeVariables': {'fontSize': '15px'}, 'flowchart': {'curve': 'linear', 'nodeSpacing': 30, 'rankSpacing': 40}}}%%
flowchart TB
    QUESTION["❓ User question"]
    RETRIEVE["Hybrid retrieval<br/>keyword + vector similarity"]
    RERANK["Cross-encoder reranking<br/>score query–chunk pairs"]
    GENERATE["Grounded generation<br/>question + reranked context"]
    CHECK{"Evidence<br/>sufficient?"}
    ANSWER["✅ Cited answer<br/>+ source references"]
    ABSTAIN["⛔ Abstention<br/>'I don't know'"]

    QDRANT[("Qdrant<br/>vector index")]
    SQLITE[("SQLite<br/>provenance")]

    QUESTION --> RETRIEVE
    RETRIEVE --> RERANK
    RERANK --> GENERATE
    GENERATE --> CHECK
    CHECK -->|yes| ANSWER
    CHECK -->|no| ABSTAIN

    QDRANT -.-> RETRIEVE
    SQLITE -.-> GENERATE

    classDef process fill:#D1FAE5,stroke:#047857,color:#064E3B,stroke-width:1.5px
    classDef store fill:#FEF3C7,stroke:#B45309,color:#78350F,stroke-width:1.5px
    classDef llm fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,stroke-width:1.5px
    classDef question fill:#DBEAFE,stroke:#1E40AF,color:#1E3A8A,stroke-width:1.5px

    class QUESTION question
    class RETRIEVE,RERANK process
    class GENERATE,CHECK,ANSWER,ABSTAIN llm
    class QDRANT,SQLITE store
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
| Embeddings | [BGE-M3](https://bge-model.com/bge/bge_m3.html) | Multilingual vector representations | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Retrieval | [Qdrant](https://qdrant.tech/documentation/search/text-search/hybrid-search/) | Dense/sparse hybrid search and fusion | <img src='https://cdn.simpleicons.org/qdrant/DC244C' alt='Qdrant' title='Qdrant' height='20' /> |
| Reranking | [`bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) · CrossEncoder | Candidate reranking | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Metadata | SQLite · PostgreSQL-ready | Documents, status, evaluation, and audit data | <img src='https://cdn.simpleicons.org/sqlite/003B57' alt='SQLite' title='SQLite' height='20' /> |
| Storage | Local filesystem | Uploads and processed artifacts | — |
| Jobs | Python worker | Background ingestion and re-indexing | <img src='https://cdn.simpleicons.org/python/3776AB' alt='Python' title='Python' height='20' /> |
| Generation | Gemini 2.5 Flash-Lite (free tier for demo) · `google-genai` | Grounded answer generation | <img src='https://cdn.simpleicons.org/googlegemini/8E75B2' alt='Gemini' title='Gemini' height='20' /> |
| Tooling | `uv` · `pnpm` | Python and Node.js dependencies | <img src='https://cdn.simpleicons.org/uv/6E56CF' alt='uv' title='uv' height='20' /> <img src='https://cdn.simpleicons.org/pnpm/F69220' alt='pnpm' title='pnpm' height='20' /> |

## Evaluation framework

A reliable RAG system needs to be evaluated at every important boundary, from document extraction to the final answer. FORGE uses three pillars: a golden dataset, a consistent metric set, and repeatable evaluation tooling.

### 1. The golden dataset

The golden dataset is human-authored input included in each evaluation test case. Each case contains the question, source evidence, and expected answer; that expected answer is the ground truth used to evaluate retrieval, generation, correctness, and abstention.

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

When Docling, BGE-M3, Qdrant, and local storage run locally, ingestion is approximately **$0.00 per document**. Visual analysis is also free while it remains within the Gemini free tier; paid VLM usage makes the cost document-dependent.

##### 3. Monthly demo TCO

| Component | Monthly estimate |
|---|---:|
| Oracle Cloud VPS (Always Free) | $0 |
| Gemini API (10,000 queries) | $2.10 |
| Gemini visual analysis within free tier | $0 |
| Self-hosted services and local storage | $0 |
| **Estimated total** | **$2.10/month** |

The total excludes paid VLM overages, evaluation calls, and future managed-service costs.

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

## Repository Rules
1. Discuss ideas through Zalo first before building and sending a pull requests.
