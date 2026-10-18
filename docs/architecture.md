# System Architecture

This document tracks the incremental system design of the Agentic RAG system across development stages.

---

## 1. Implemented Architecture

```
[Raw Files: PDF, DOCX, MD, TXT]
              │
              ▼
    Format Detection (Extension)
              │
              ▼
   Format-Specific Parsers
    ├── PdfParser       (page text + physical page_number)
    ├── DocxParser      (headings + paragraphs)
    ├── MarkdownParser  (ATX header hierarchy + section_title)
    └── TxtParser       (validated encoding fallback: UTF-8 / CP1252)
              │
              ▼
   Conservative Normalization
    - CRLF/CR -> LF
    - Non-printable control char stripping (keeps \t, \n)
    - Consecutive newline collapsing (3+ -> 2)
    - Line-trailing whitespace removal
              │
              ▼
   Canonical Document Representation
    ├── Document (id, filename, title, file_type, source_path, content_hash, metadata)
    └── DocumentSection (id, document_id, section_index, page_number, section_title, text)
              │
              ▼
   SQLite Repository (PRAGMA foreign_keys = ON)
    ├── Table: documents (content_hash UNIQUE)
    ├── Table: document_sections (UNIQUE(document_id, section_index), CASCADE ON DELETE)
    └── Table: document_chunks (UNIQUE(section_id, chunk_index), CASCADE ON DELETE)
              │
              ▼
   Document Chunking Subsystem (app.chunking)
    ├── Tokenizer Abstraction (TiktokenTokenizer: cl100k_base)
    ├── SectionChunker (Unicode-safe, exact substring invariant, sliding window)
    └── ChunkingService & CLI (chunk, chunk-all, list, inspect)
```

### Components Implemented to Date

#### Foundation & Service Layer
* **FastAPI Backend (`backend/app`)**:
  * `core/config.py`: Environment-driven configuration via `pydantic-settings`.
  * `api/health.py`: Health check router (`GET /health`, `GET /api/health`).
  * `main.py`: Application factory with CORS middleware.
* **React + Vite Frontend (`frontend/src`)**:
  * Diagnostic status panel monitoring backend health and roundtrip latency.

#### Ingestion & Corpus Representation Layer
* **Canonical Document Models (`backend/app/ingestion/models.py`)**:
  * `Document`: Content-addressable identifier derived deterministically from SHA-256 content hash (UUIDv5), original filename, title, file type, normalized relative source path, raw metadata, timestamps, and ordered sections.
  * `DocumentSection`: Preserves structural anchors (`page_number` for PDF, `section_title` for Markdown/DOCX, and sequential `section_index`).
* **Text Normalizer (`backend/app/ingestion/normalizer.py`)**:
  * Conservative text standardizer preserving code formatting, tabs, diacritics, mathematical Unicode, and paragraph boundaries.
* **Format-Specific Parsers (`backend/app/ingestion/parsers/`)**:
  * `PdfParser`: Extracts text per page using `pypdf`, preserving physical page numbers and PDF document metadata.
  * `DocxParser`: Extracts sections delineated by Heading styles using `python-docx`, maintaining heading hierarchy and document properties.
  * `MarkdownParser`: Splits documents by Markdown ATX headings (`#` through `######`), preserving section titles and body text.
  * `TxtParser`: Decodes text with explicit encoding validation (UTF-8, UTF-8-SIG, CP1252), rejecting corrupted text without blind Latin-1 fallback.
* **Storage Layer (`backend/app/ingestion/storage/repository.py`)**:
  * SQLite persistence with strict foreign key constraints (`PRAGMA foreign_keys = ON`), automatic table and index initialization, and compound uniqueness constraint on `(document_id, section_index)`.

#### Document Chunking Subsystem
* **Tokenizer Abstraction (`backend/app/chunking/tokenizer.py`)**:
  * `BaseTokenizer`: Replaceable token counting and encoding interface.
  * `TiktokenTokenizer`: Production BPE tokenizer wrapping `cl100k_base`.
  * `CharacterTokenizer`: Deterministic test-only implementation.
* **Section-Aware Chunk Splitter (`backend/app/chunking/splitter.py`)**:
  * Splits each `DocumentSection` independently, strictly preventing chunks from crossing physical PDF pages or section headers.
  * Sliding window algorithm respecting configurable token limits (`chunk_size=400`, `chunk_overlap=60`).
  * Guaranteed invariant: `section.text[chunk.start_char:chunk.end_char] == chunk.text` for all chunks, verified across complex Unicode, emojis, math symbols, code blocks, and diacritics.
  * Evaluated token count verification: `chunk.token_count <= chunk_size`.
* **Normalized Chunk Storage & Provenance (`backend/app/ingestion/storage/repository.py`)**:
  * Table `document_chunks` references `section_id` with `FOREIGN KEY (section_id) REFERENCES document_sections (id) ON DELETE CASCADE` and `UNIQUE (section_id, chunk_index)`.
  * `document_id` and document/section metadata (filename, source path, title, page number, section title) are derived via relational `JOIN`, eliminating redundant denormalization and preventing inconsistent document-section relationships.
  * Transactional rebuilding: running with `--rebuild` deletes previous chunks and inserts replacement chunks in a single atomic transaction.
* **Chunking Service & CLI (`backend/app/chunking/`)**:
  * `ChunkingService`: Idempotent single-document and batch corpus chunking with per-document error isolation.
  * CLI (`python -m app.chunking`): Subcommands `chunk`, `chunk-all`, `list`, and `inspect`.

#### Corpus Explorer & Developer Workbench
* **Read-Only Corpus API (`backend/app/api/`)**:
  * `api/schemas.py`: Explicit Pydantic response models (`CorpusStatsResponse`, `DocumentListItem`, `DocumentDetailResponse`, `PaginatedChunksResponse`, `ChunkItem`).
  * `api/documents.py`: Read-only exploration endpoints mounted under `/api`:
    * `GET /api/stats`: Aggregate counts for documents, sections, chunks, and summed chunk tokens.
    * `GET /api/documents`: Catalog listing with joined section, chunk, and summed chunk-token counts.
    * `GET /api/documents/{id}`: Detailed metadata and section structure with 200-character preview snippets.
    * `GET /api/documents/{id}/chunks`: Paginated chunk inspection with exact section-relative character offsets `[start_char : end_char)` and section provenance.
  * Security & Minimal Surface: Local filesystem paths (`source_path`) are excluded from API schemas. All writes remain strictly on the CLI.
* **Developer Workbench UI (`frontend/src/`)**:
  * Utilitarian, high-density interface with zero third-party component libraries or routing dependencies.
  * Three in-app tabs:
    1. **Knowledge Base** (default): Filterable document table, format badges, and split inspection drawer showing document metadata and ordered section breakdown.
    2. **Chunk Explorer**: Document picker, pagination controls, token badges, section provenance badges, exact section character spans `[start_char : end_char)` relative to section text, and scrollable monospace verbatim text viewer with copy action.
    3. **Diagnostics**: Real-time backend connectivity verification and roundtrip latency monitoring.
  * Pinned compact corpus summary bar displaying total documents, sections, chunks, and summed chunk tokens (clarified as including overlap).

---

## 2. Target Agentic RAG Architecture

> The components described below represent the planned agentic retrieval, verification, and evaluation pipeline that builds upon the current corpus and chunking foundation.

```
User Query / Task
       │
       ▼
┌───────────────────────────────┐
│         Task Analyzer         │  Classifies task type, scope, and retrieval necessity
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│            Planner            │  Decomposes multi-part queries into executable sub-goals
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│     Retrieval Controller      │  Selects retrieval strategies based on task profile
└──────────────┬────────────────┘
               │
               ├──────────────────────────────────────────┐
               │                                          │
               ▼                                          ▼
┌───────────────────────────────┐          ┌───────────────────────────────┐
│   Semantic / Vector Search    │          │  Keyword (Custom BM25) Search │
│   (FAISS + Open Embedding)    │          │  + Metadata Filters           │
└──────────────┬────────────────┘          └──────────────┬────────────────┘
               │                                          │
               └────────────────────┬─────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────┐
│                        Reranker                         │  Cross-encoder score re-ranking
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Evidence Evaluator                   │  Filters noise and assesses relevance
└───────────────────────────┬─────────────────────────────┘
                            │
               [Evidence Insufficient / Gaps]
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                Adaptive Retrieval Loop                  │  Reformulates query / triggers multi-hop
└───────────────────────────┬─────────────────────────────┘
                            │ [Evidence Sufficient]
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Answer Generator                     │  Synthesizes grounded response
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Claim Extraction                     │  Isolates atomic factual claims
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   Answer Verification                   │  Cross-checks claims against retrieved docs
└───────────────────────────┬─────────────────────────────┘
                            │
               [Contradictions / Unsupported Claims]
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     Self-Correction                     │  Reprompts / rewrites to eliminate hallucinations
└───────────────────────────┬─────────────────────────────┘
                            │ [Verified Grounded]
                            ▼
Final Output: Verified Answer + Inline Citations + Agent Execution Trace
```

### Planned Future Subsystems

1. **Dense & Sparse Indexing**:
   * Dense semantic embeddings using open-source models with local FAISS index.
   * Lexical search via custom, dependency-free BM25 indexing.
   * Reciprocal Rank Fusion (RRF) for hybrid query resolution.
2. **Adaptive Controller & Planner**:
   * Query decomposition into sub-goals and iterative multi-hop retrieval.
3. **Verification & Self-Correction**:
   * Atomic claim extraction and NLI-based factual cross-checking against retrieved citations.
