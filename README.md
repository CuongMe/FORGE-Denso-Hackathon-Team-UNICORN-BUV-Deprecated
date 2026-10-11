<p align="center">
  <img src="./image-1.png" alt="UNICORN logo for FORGE" width="120" />
</p>

<h1 align="center">FORGE: Factory Operations Retrieval &amp; Generation Engine</h1>

<p align="center">
  <strong>Multimodal factory document intelligence for grounded, traceable answers.</strong><br />
  Denso Factory Hackathon 2026 · Challenge A3
</p>

FORGE is a multi-format document understanding and retrieval-augmented generation (RAG) system. It is designed to process PDFs, images, tables, and bilingual documents using OCR/VLM, layout-aware extraction, multilingual embeddings, and vector search - enabling accurate chatbot responses without manual preprocessing.

## Product demo

<p align="center">
  <img src="./docs/forge-demo-preview.gif" alt="Full 72-second FORGE product demonstration" width="100%" />
</p>

## Team UNICORN

* Team Member 1: Phan Tuấn Minh - Team Leader - Software Engineering Year 2
* Team Member 2: Phan Khánh Linh - UI/UX Design/Business Analyst - Data Science & AI Year 1
* Team Member 3: Nguyễn Tuấn Anh - Data Curator - Data Science & AI Year 2
* Team Member 4: Trần Hoàng Cường - Agile Developer - Data Science & AI Year 3 (Repo Owner)
* Team Member 5: Bùi Minh Tiến - Technical Specialist - Software Engineering Year 2

All team members contributed significantly to this project*
## Pain point

Factory operations knowledge is often spread across PDFs, scanned images, tables, and bilingual documents. Each format can require different preprocessing, including OCR, layout reconstruction, table extraction, and language handling, before an AI system can search and use the content. When that work is manual or inconsistent, valuable information takes longer to access and chatbot answers can miss or misread important context. This makes it difficult to build one dependable retrieval workflow for the documents teams already use.

## Unique selling point

1. FORGE is being fine-tuned for factory environments and aiming for seamless integration with DensoGPT.
2. Its local-first full-stack design keeps hosting costs close to zero.
3. FORGE is a hardened RAG pipeline engineered for production reliability. Checkpointed ingestion, retries, and idempotent writes prevent data loss and duplication. Being fully self-hosted, it also preserves data privacy — no factory documents leave the premises.

## Data Curation

The project uses three datasets: a multilingual golden set, curated external test data, and an AI-generated factory pack.

| Dataset | Contents and purpose |
|---|---|
| **Golden dataset** | [`golden_dataset_25_multilingual.csv`](data/evaluation/golden_dataset_25_multilingual.csv): 25 factory questions with expected answers (15 Vietnamese, 5 Japanese, 5 English), ready for recording answers and review. |
| **Curated data** | [Dataset notes and included files](data/curated_forge_testing/README.md): 30 [JA-Business-Doc-RQ-Bench](https://huggingface.co/datasets/stockmark/JA-Business-Doc-RQ-Bench) images with Q&A metadata, plus [`industrial_dataset.csv`](data/curated_forge_testing/tabular/industrial_dataset.csv). VIXIO samples remain local until redistribution terms are confirmed. |
| **AI-generated pack** | [`data/denso_factory_hack_data_prep`](data/denso_factory_hack_data_prep): synthetic factory PDFs, scans, images, spreadsheets, and CSVs for testing ingestion, OCR, visual analysis, retrieval, and UI flows. |

### Curation Principles

1. **Preserve provenance:** Keep each sample linked to its original source, dataset, metadata, and available ground truth.
2. **Cover factory formats:** Include documents, scans, tables, images, CSV/XLS/XLSX, PowerPoint, and TXT files, plus bilingual Vietnamese/Japanese content.
3. **Separate test purposes:** Use the golden dataset for answer evaluation, curated data for repeatable external-source tests, and the AI-generated pack for functionality testing.
4. **Keep evaluation honest:** Label synthetic data, retain human-reviewed answers or masks, and leave unavailable ground truth unfilled.

## Market Research & Analysis

FORGE sits between managed enterprise search, open-source document-RAG platforms, and industrial copilots. The alternatives below are adjacent rather than identical competitors:

| Alternative | Current strength | FORGE's position |
|---|---|---|
| [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview?tabs=docs) | Managed hybrid retrieval, semantic ranking, agentic retrieval, and multimodal document extraction. | A smaller, local-first factory pipeline with direct control over parsing, models, and evidence policy. |
| [Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-multimodal.html) | Managed multimodal ingestion and retrieval across text, images, audio, and video. | Focused on the factory document formats and bilingual evidence flows needed for the A3 demo. |
| [Google Agent Search](https://docs.cloud.google.com/generative-ai-app-builder/docs) | Managed enterprise search, semantic understanding, structured data, PDFs, and generated answers. | Lower-cost, self-hostable architecture with an explicit ingestion trace and abstention path. |

### Positioning

The market is crowded at the generic RAG layer. FORGE should therefore be positioned as a practical factory-document intelligence layer: local-first, multimodal, bilingual, source-cited, and safe to abstain when evidence is weak. Its strongest wedge is the combination of layout-aware ingestion, hybrid retrieval, visual evidence handling, and a repeatable factory evaluation set—not a claim that its individual models are unique.

### Related research

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) established the core pattern of grounding generation with retrieved external knowledge.
- [BGE-M3](https://arxiv.org/abs/2402.03216) supports multilingual dense, sparse, and multi-vector retrieval, which aligns with FORGE's Vietnamese/Japanese retrieval requirement.
- [DocVQA](https://arxiv.org/abs/2007.00398) shows that document question answering depends on structure, layout, and reading comprehension—not OCR alone.
- [MMDocRAG](https://arxiv.org/abs/2505.16470) finds that multimodal document QA still struggles with cross-modal evidence retrieval, supporting FORGE's emphasis on visual evidence and explicit evaluation.

The main gaps versus mature enterprise products are connectors, identity-aware permissions, high-availability workers, and measured benchmark results. These should be framed as the next production milestones rather than hidden behind generic RAG claims.

## Solution architecture

FORGE uses a multimodal retrieval-augmented generation pipeline. The indexing path converts mixed-format documents into searchable, context-preserving representations. The answering path combines a user's question with the most relevant content and passes both to an LLM for a grounded response.

The pilot can index ASCII DXF blueprints, including labels, layers, dimension values, and common 2D geometry. Export DWG files as ASCII DXF before upload; direct DWG, binary DXF, and visual drawing interpretation are not supported yet.


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

## Quick start

1. Install the locked backend dependencies: `cd services/api && uv sync`.
2. Copy `services/api/.env.example` to `services/api/.env` and set `GEMINI_API_KEY`.
3. Start Qdrant locally on `http://127.0.0.1:6333`, or point `FORGE_QDRANT_URL` at a Qdrant Cloud instance.
4. Build the source index once: `uv run python -m app.index_demo`.
5. Start the API with `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Start the frontend in a second terminal: `cd apps/web && pnpm install && pnpm dev`.

The API reports `ready: false` until Qdrant is reachable and the source index has been built.

### Real service engine

The real service engine is planned for future implementation in the [`services/`](services/) folder. The live Vercel site is a preprocessed demo and is separate from that backend.

### Vercel demo

Live demo: [https://forge-factory-demo.vercel.app](https://forge-factory-demo.vercel.app/)

Run it locally from Git:

```sh
git clone https://github.com/CuongMe/FORGE-Denso-Hackathon-Team-UNICORN-BUV-ongoing.git
cd FORGE-Denso-Hackathon-Team-UNICORN-BUV-ongoing/apps/web
cp .env.vercel.example .env.local
pnpm install
pnpm dev
```

Set `GEMINI_API_KEY` in `.env.local` to enable live Gemini answers; Upstash credentials are only needed when deployed. The demo uses a preprocessed corpus and BM25 retrieval, separate from the system backend in `services/`.

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
| Visual understanding | [Florence-2](https://huggingface.co/microsoft/Florence-2-base-ft) | Local visual captions with human review | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Florence-2 on Hugging Face' height='20' /> |
| Embeddings | [BGE-M3](https://bge-model.com/bge/bge_m3.html) | Multilingual vector representations | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Retrieval | [Qdrant](https://qdrant.tech/documentation/search/text-search/hybrid-search/) (self-hosted) | Dense/sparse hybrid search and fusion | <img src='https://cdn.simpleicons.org/qdrant/DC244C' alt='Qdrant' title='Qdrant' height='20' /> |
| Reranking | [`bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) · CrossEncoder | Candidate reranking | <img src='https://cdn.simpleicons.org/huggingface/FFD21E' alt='Hugging Face' title='Hugging Face model ecosystem' height='20' /> |
| Aggregation | SQLite in-memory (`sqlite3`) | SQL `COUNT`, `SUM`, `AVG`, `MIN`, and `MAX` over selected tabular data; returns a source-cited result and falls back to RAG when it cannot execute the aggregation | <img src='https://cdn.simpleicons.org/sqlite/003B57' alt='SQLite' title='SQLite' height='20' /> |
| Metadata | SQLite · PostgreSQL-ready | Documents, status, evaluation, and audit data | <img src='https://cdn.simpleicons.org/sqlite/003B57' alt='SQLite' title='SQLite' height='20' /> |
| Storage | Local filesystem | Uploads and processed artifacts | — |
| Jobs | Python worker | Background ingestion and re-indexing | <img src='https://cdn.simpleicons.org/python/3776AB' alt='Python' title='Python' height='20' /> |
| Generation | Configurable Gemini model · `google-genai` | Grounded answer generation | <img src='https://cdn.simpleicons.org/googlegemini/8E75B2' alt='Gemini' title='Gemini' height='20' /> |
| Tooling | `uv` · `pnpm` | Python and Node.js dependencies | <img src='https://cdn.simpleicons.org/uv/6E56CF' alt='uv' title='uv' height='20' /> <img src='https://cdn.simpleicons.org/pnpm/F69220' alt='pnpm' title='pnpm' height='20' /> |

## Evaluation framework

A reliable RAG system needs to be evaluated at every important boundary, from document extraction to the final answer. FORGE includes a manual multilingual test set for checking its factory-document retrieval and answers.

### Manual multilingual test set

[`golden_dataset_25_multilingual.csv`](data/evaluation/golden_dataset_25_multilingual.csv) contains 25 source-backed questions: 15 Vietnamese, 5 Japanese, and 5 English. It includes expected answers and blank fields for recorded answers, review checkboxes, and notes. The corpus is synthetic demo data, not official DENSO operational data.

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

Before hosting, check the current Gemini price for the configured model and the VM, disk, IPv4, and transfer prices in the chosen cloud region. Record actual token and infrastructure usage during the demo. Local inference still consumes paid VM time and storage; there is no guaranteed free monthly total.

### License

This project is licensed under the [Apache License 2.0](LICENSE).

### Baseline comparison

Compare both systems on the same reviewed answerable question set:

- **Naive baseline:** fixed-size chunking, dense-only retrieval, no cross-encoder reranking, and the same generation model where possible.
- **FORGE:** Docling `HybridChunker`, hybrid dense and sparse retrieval, cross-encoder reranking, and the same generation model.

The current abstention holdout cannot support this comparison. Use `TBD` until a reviewed answerable question set is available and the experiment is run.

| Category | Metric | baseline | FORGE | Change |
|---|---|---:|---:|---:|
| Retrieval | Context recall | TBD | TBD | TBD |
| Retrieval | Reranker lift, MRR | N/A | TBD | TBD |
| Generation | Faithfulness | TBD | TBD | TBD |
| Generation | Answerability F1 | TBD | TBD | TBD |
| Operations | p95 latency | TBD | TBD | TBD |
| Operations | Cost per query | TBD | TBD | TBD |

