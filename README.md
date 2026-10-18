# Agentic RAG

An adaptive, agent-driven Retrieval-Augmented Generation (RAG) system built from first principles for research and knowledge-intensive tasks.

---

## Project Overview

Standard RAG pipelines follow a rigid, single-pass pattern: retrieve top-\(k\) chunks, stuff them into a prompt, and generate a response. In practice, this breaks down on complex or ambiguous tasks where queries require multi-step reasoning, evidence evaluation, query reformulation, or factual verification.

This project implements an **Agentic RAG** architecture designed to:
* Classify incoming queries and adaptively determine retrieval requirements.
* Decompose multi-step questions into reasoned sub-goals.
* Query hybrid indices (custom BM25 keyword search, dense FAISS semantic search, and metadata filtering).
* Evaluate retrieved evidence quality and dynamically trigger secondary retrieval passes if evidence is insufficient.
* Extract atomic factual claims from generated answers and verify them against source passages.
* Self-correct drafts when claims fail verification.
* Produce fully grounded responses with granular citations and execution traces.

The project is built intentionally with minimal reliance on monolithic agent/RAG frameworks (such as LangChain or LangGraph) to keep execution transparent, modular, and directly benchmarkable.

---

## Core Architecture & Implemented Subsystems

AdaptiveRAG is designed as a modular pipeline with clear separation of concerns across ingestion, normalization, chunking, persistence, and developer exploration tools.

### 1. Service Layer & System Diagnostics (`backend/app/core`, `frontend/src`)
* **Backend**: Modular FastAPI service exposing an environment-aware `/health` status endpoint with CORS middleware configured for development.
* **Diagnostics Panel**: High-precision probe reporting backend health, environment status, and live HTTP roundtrip latency in milliseconds.
* **Configuration**: Structured environment variable management using `pydantic-settings` (`backend/.env.example`) and Vite environment variables (`frontend/.env.example`).
* **Tooling & Git**: Production `.gitignore` ignoring virtualenvs, node modules, build artifacts, and secrets while preserving IDE team settings.

### 2. Document Ingestion & Corpus Representation (`backend/app/ingestion`)
* **Supported Formats**:
  * **PDF** (`.pdf`): Extracts page text using `pypdf`, preserving physical `page_number` anchors and PDF metadata.
  * **DOCX** (`.docx`): Extracts sections grouped by Heading styles using `python-docx`, maintaining heading hierarchy and document properties.
  * **Markdown** (`.md`, `.markdown`): Identifies ATX header hierarchies (`#` through `######`), segmenting content with `section_title` preserved.
  * **TXT** (`.txt`): Validated encoding fallback (UTF-8, UTF-8-SIG, CP1252), rejecting unreadable text without blind Latin-1 corruption.
* **Conservative Text Normalization**:
  * Converts CRLF/CR to LF, removes non-printable control characters while preserving tabs and newlines, collapses excessive blank lines, and preserves meaningful Unicode (math symbols, diacritics, quotes, code indentation).
* **Canonical Document Representation**:
  * Decoupled internal representation (`Document` and `DocumentSection`) with deterministic content-addressable identifiers (derived via SHA-256) and portable relative source paths.
* **SQLite Persistence**:
  * Local relational storage (`data/corpus.db`) with `PRAGMA foreign_keys = ON`, cascade deletion, unique constraint on `(document_id, section_index)`, and atomic transactional replacements.
* **Ingestion CLI (`app.ingestion`)**:
  * Tooling for directory batch scanning, duplicate resolution, document inspection, and corpus management.

### 3. Document Chunking & Provenance Storage (`backend/app/chunking`)
* **Tokenizer Abstraction (`app.chunking.tokenizer`)**:
  * Replaceable `BaseTokenizer` protocol with `TiktokenTokenizer` using `cl100k_base` BPE encoding.
  * Strict parameter validation: `chunk_size > 0` and `0 <= chunk_overlap < chunk_size`.
* **Section-Aware Chunking (`app.chunking.splitter`)**:
  * Chunks each `DocumentSection` independently, strictly preserving physical PDF page and heading boundaries.
  * Default configuration: 400 tokens per chunk with 60 tokens of overlap.
  * Invariant: `section.text[chunk.start_char:chunk.end_char] == chunk.text` for all chunks, including complex Unicode, emojis, math symbols, code blocks, and combining marks.
  * Evaluated token limit verification: every chunk satisfies `token_count <= chunk_size`.
* **Normalized Relational Chunk Storage**:
  * `document_chunks` table linked to `document_sections(id)` via `ON DELETE CASCADE` and `UNIQUE(section_id, chunk_index)`.
  * `document_id` and document/section metadata are derived through relational joins, preventing inconsistent document-section mappings.
  * Transactional rebuilding: running with `--rebuild` atomically replaces existing chunks in a single transaction.
* **Chunking CLI (`app.chunking`)**:
  * Tooling for single-document chunking, corpus-wide batch chunking, chunk summary listing, and deep chunk inspection with full source provenance.

### 4. Corpus Explorer & Developer Workbench (`backend/app/api`, `frontend/src`)
* **Read-Only Corpus API (`app.api`)**:
  * `GET /api/stats`: High-level aggregate counts of documents, sections, chunks, and summed chunk tokens.
  * `GET /api/documents`: Catalog list with joined section, chunk, and summed chunk-token counts.
  * `GET /api/documents/{document_id}`: Document details and structural section list with 200-character preview snippets.
  * `GET /api/documents/{document_id}/chunks`: Paginated chunk inspection with exact section-relative character offsets `[start_char : end_char)` and section provenance.
  * Explicit Pydantic response models; local machine paths (`source_path`) excluded from API surface.
* **Developer Workbench UI (`frontend/src`)**:
  * Utilitarian React interface (zero third-party UI/routing libraries) with in-app tab state:
    * **Knowledge Base** (default): Filterable document table, format badges, and split inspection drawer showing document metadata and ordered section breakdown.
    * **Chunk Explorer**: Document picker, pagination controls, token badges, section provenance badges, exact section character spans `[start_char : end_char)` relative to section text, and scrollable monospace verbatim text viewer with copy action.
    * **Diagnostics**: Real-time backend connectivity verification and roundtrip latency monitoring.
  * Compact single-line corpus summary strip pinned above the active view with manual refresh button.

---

## Roadmap

Planned future subsystems:
* Dense embeddings generation and local FAISS vector indexing.
* Custom BM25 keyword index and hybrid fusion (RRF).
* Cross-encoder reranking and relevance filtering.
* LLM provider abstractions and adaptive agent controller loops.
* Multi-hop query decomposition and adaptive retrieval strategies.
* Claim extraction, NLI-based fact verification, and self-correction.
* Grounded generation interface, citation inspector, and agent trace visualizer.
* Benchmark datasets and comparative RAG evaluation metrics.

---

## Tech Stack

* **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings
* **Ingestion & Parsers**: `pypdf` (PDF), `python-docx` (DOCX), Python standard library (Markdown, TXT)
* **Chunking & Tokenization**: `tiktoken` (`cl100k_base`), `SectionChunker`
* **Storage**: SQLite (`sqlite3`) with strict foreign keys
* **Frontend**: React 18, Vite 5, JavaScript / CSS
* **Testing**: Pytest, HTTPX / Starlette TestClient

---

## Repository Structure

```
adaptiveRAG/
├── .gitignore                   # Excludes venvs, node_modules, build artifacts, secrets, *.db
├── README.md                    # Project documentation and setup instructions
├── docs/
│   └── architecture.md          # Implemented architecture vs target Agentic RAG architecture
├── data/                        # Local document corpus and SQLite database storage
├── backend/
│   ├── .env.example             # Example backend environment variables
│   ├── requirements.txt         # Pinned backend dependencies
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application factory and entry point
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py        # Pydantic BaseSettings configuration
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── health.py        # Health check router (/health, /api/health)
│   │   │   ├── schemas.py       # Corpus explorer Pydantic response models
│   │   │   └── documents.py     # Corpus explorer read-only API router
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py      # CLI entry point (python -m app.ingestion)
│   │   │   ├── cli.py           # CLI commands (ingest, list, inspect, delete)
│   │   │   ├── models.py        # Canonical Document and DocumentSection models
│   │   │   ├── normalizer.py    # Conservative text normalizer
│   │   │   ├── service.py       # Ingestion orchestrator & duplicate resolver
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py      # Abstract BaseParser class
│   │   │   │   ├── docx_parser.py
│   │   │   │   ├── markdown_parser.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   └── txt_parser.py
│   │   │   └── storage/
│   │   │       ├── __init__.py
│   │   │       └── repository.py # SQLite DocumentRepository
│   │   └── chunking/
│   │       ├── __init__.py
│   │       ├── __main__.py      # CLI entry point (python -m app.chunking)
│   │       ├── cli.py           # CLI commands (chunk, chunk-all, list, inspect)
│   │       ├── models.py        # DocumentChunk & ChunkWithProvenance models
│   │       ├── tokenizer.py     # BaseTokenizer & TiktokenTokenizer
│   │       ├── splitter.py      # Unicode-safe SectionChunker
│   │       └── service.py       # ChunkingService coordinator
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py          # Shared pytest fixtures
│       ├── generate_fixtures.py # Deterministic synthetic fixture generator
│       ├── test_health.py       # Health check tests
│       ├── test_ingestion.py    # Ingestion, parser, and persistence test suite
│       ├── test_chunking.py     # Chunking, tokenizer, boundary, and offset test suite
│       └── test_api_documents.py # Corpus Explorer API test suite
└── frontend/
    ├── .env.example             # Example frontend environment variables
    ├── package.json             # React + Vite package configuration
    ├── vite.config.js           # Vite configuration
    ├── index.html               # Single-page application entry HTML
    └── src/
        ├── main.jsx             # React root mounting
        ├── api.js               # Centralized API client with latency tracking
        ├── App.jsx              # Main workbench shell (3-tab in-app navigation)
        ├── App.css              # Utilitarian workbench styling
        ├── index.css            # Base reset styles
        └── components/
            ├── Header.jsx           # App brand, nav tabs, and live health pill
            ├── CorpusSummaryBar.jsx # Compact corpus count strip + refresh button
            ├── KnowledgeBaseView.jsx # Document table, filter, and section inspector
            ├── ChunkExplorerView.jsx # Document chunk viewer, pagination, and offset inspector
            └── SystemStatusView.jsx  # System health and latency diagnostic probe
```

---

## Getting Started

### Prerequisites
* Python 3.12 installed
* Node.js (v20+ LTS recommended) and npm installed
* Git

---

### Backend Setup

1. Open a terminal in the project root:
   ```bash
   cd backend
   ```

2. Create and activate a dedicated virtual environment:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create local configuration file from the template:
   ```bash
   cp .env.example .env
   ```

5. Run all tests:
   ```bash
   pytest tests
   ```

6. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Interactive API docs are available at `http://127.0.0.1:8000/docs`.

---

### Document Ingestion CLI

The ingestion CLI manages document parsing, normalization, and local corpus persistence.

Set your `PYTHONPATH` to `backend` (or run from the `backend/` directory):

* **Windows (PowerShell)**:
  ```powershell
  $env:PYTHONPATH="backend"
  ```
* **Linux / macOS**:
  ```bash
  export PYTHONPATH="backend"
  ```

#### 1. Ingest a Directory or File
```bash
python -m app.ingestion ingest path/to/documents
```
Options:
* `--on-duplicate skip` (default): Skips files whose SHA-256 content matches an already-ingested document.
* `--on-duplicate replace`: Atomically replaces existing document and cascaded sections.
* `--no-recursive`: Ingests top-level files only.
* `--db <path>`: Specifies custom SQLite database path (defaults to `CORPUS_DB_PATH` in `.env`).

#### 2. List Ingested Documents
```bash
python -m app.ingestion list
```

#### 3. Inspect a Document
```bash
python -m app.ingestion inspect <document_id>
```

#### 4. Delete a Document
```bash
python -m app.ingestion delete <document_id>
```

---

### Document Chunking CLI

The chunking CLI manages section-aware splitting and chunk persistence.

#### 1. Chunk All Ingested Documents
```bash
python -m app.chunking chunk-all
```
Options:
* `--rebuild`: Atomically deletes and replaces existing chunks for all documents.
* `--chunk-size <int>`: Overrides default token capacity (default: 400).
* `--chunk-overlap <int>`: Overrides default token overlap (default: 60).
* `--db <path>`: Specifies custom SQLite database path.

#### 2. Chunk a Single Document
```bash
python -m app.chunking chunk <document_id> [--rebuild]
```

#### 3. List Chunk Summaries Across Corpus
```bash
python -m app.chunking list [--document-id <document_id>]
```
Displays document ID, chunk count, total tokens, average tokens per chunk, and filename.

#### 4. Inspect a Chunk with Full Provenance
```bash
python -m app.chunking inspect <chunk_id>
```
Displays chunk text, token count, exact character offsets in source section, section index, heading/title, page number (for PDFs), and source file path.

---

### Frontend Setup

1. Open a separate terminal in the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create local configuration file:
   ```bash
   cp .env.example .env
   ```

4. Start the Vite development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## Verification

1. **Run full automated test suite**:
   ```bash
   pytest backend/tests
   ```
   Runs 42 tests verifying health endpoints, text normalizer, format parsers, encoding fallback, section chunking, exact substring offsets, Unicode safety, SQLite foreign key enforcement, uniqueness constraints, rebuilding, and batch failure isolation.

2. **Verify CLI batch ingestion and chunking**:
   ```powershell
   $env:PYTHONPATH="backend"
   python -m app.ingestion ingest backend/tests/fixtures
   python -m app.chunking chunk-all
   python -m app.chunking list
   ```
