"""SQLite repository for canonical document persistence."""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from app.chunking.models import ChunkSummary, ChunkWithProvenance, DocumentChunk
from app.ingestion.models import Document, DocumentSection, DocumentSummary


class DocumentRepository:
    """Manages transactional SQLite storage for canonical documents and sections."""

    def __init__(self, db_path: str = "data/corpus.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with foreign key constraints enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database tables, foreign keys, and indexes automatically."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    title TEXT,
                    file_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    section_index INTEGER NOT NULL,
                    page_number INTEGER,
                    section_title TEXT,
                    text TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
                    UNIQUE (document_id, section_index)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sections_document_id ON document_sections(document_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    section_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (section_id) REFERENCES document_sections (id) ON DELETE CASCADE,
                    UNIQUE (section_id, chunk_index)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_section_id ON document_chunks(section_id);"
            )

    def find_by_content_hash(self, content_hash: str) -> Optional[Document]:
        """Look up existing document by content SHA-256."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_document(conn, row)

    def get_document(self, document_id: str) -> Optional[Document]:
        """Fetch document and its ordered sections by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_document(conn, row)

    def save_document(self, doc: Document, on_duplicate: str = "skip") -> bool:
        """Persist a canonical document transactionally.

        Args:
            doc: Canonical Document instance.
            on_duplicate: Duplicate policy ('skip' or 'replace').

        Returns:
            True if inserted or replaced, False if skipped.
        """
        with self._get_connection() as conn:
            existing = conn.execute(
                "SELECT id, source_path FROM documents WHERE content_hash = ?",
                (doc.content_hash,),
            ).fetchone()

            if existing:
                if on_duplicate == "skip":
                    return False
                elif on_duplicate == "replace":
                    # Delete existing record; cascading deletes sections due to foreign keys
                    conn.execute("DELETE FROM documents WHERE id = ?", (existing["id"],))
                else:
                    raise ValueError(f"Unknown on_duplicate policy: {on_duplicate}")

            conn.execute(
                """
                INSERT INTO documents (
                    id, filename, title, file_type, source_path, content_hash, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc.id,
                    doc.filename,
                    doc.title,
                    doc.file_type,
                    doc.source_path,
                    doc.content_hash,
                    json.dumps(doc.metadata),
                    doc.created_at,
                    doc.updated_at,
                ),
            )

            for section in doc.sections:
                conn.execute(
                    """
                    INSERT INTO document_sections (
                        document_id, section_index, page_number, section_title, text
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        doc.id,
                        section.section_index,
                        section.page_number,
                        section.section_title,
                        section.text,
                    ),
                )

        return True

    def list_documents(self) -> List[DocumentSummary]:
        """List all ingested documents with section counts."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.filename,
                    d.title,
                    d.file_type,
                    d.source_path,
                    d.content_hash,
                    d.created_at,
                    COUNT(s.id) AS section_count
                FROM documents d
                LEFT JOIN document_sections s ON d.id = s.document_id
                GROUP BY d.id
                ORDER BY d.created_at DESC;
                """
            ).fetchall()

            return [
                DocumentSummary(
                    id=row["id"],
                    filename=row["filename"],
                    title=row["title"],
                    file_type=row["file_type"],
                    source_path=row["source_path"],
                    content_hash=row["content_hash"],
                    section_count=row["section_count"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def delete_document(self, document_id: str) -> bool:
        """Delete document and its cascaded sections. Returns True if deleted."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cursor.rowcount > 0

    def _row_to_document(self, conn: sqlite3.Connection, doc_row: sqlite3.Row) -> Document:
        """Reconstruct canonical Document and its sections from SQLite rows."""
        section_rows = conn.execute(
            """
            SELECT id, document_id, section_index, page_number, section_title, text
            FROM document_sections
            WHERE document_id = ?
            ORDER BY section_index ASC;
            """,
            (doc_row["id"],),
        ).fetchall()

        sections = [
            DocumentSection(
                id=s["id"],
                document_id=s["document_id"],
                section_index=s["section_index"],
                page_number=s["page_number"],
                section_title=s["section_title"],
                text=s["text"],
            )
            for s in section_rows
        ]

        metadata = json.loads(doc_row["metadata"]) if doc_row["metadata"] else {}

        return Document(
            id=doc_row["id"],
            filename=doc_row["filename"],
            title=doc_row["title"],
            file_type=doc_row["file_type"],
            source_path=doc_row["source_path"],
            content_hash=doc_row["content_hash"],
            metadata=metadata,
            created_at=doc_row["created_at"],
            updated_at=doc_row["updated_at"],
            sections=sections,
        )

    def save_chunks_for_document(self, document_id: str, chunks: List[DocumentChunk]) -> None:
        """Atomically replace chunks for a document.

        Runs within a single transaction; deletes any existing chunks and inserts
        the new chunks. Rolls back cleanly on any failure.
        """
        with self._get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE section_id IN (
                        SELECT id FROM document_sections WHERE document_id = ?
                    );
                    """,
                    (document_id,),
                )
                for chunk in chunks:
                    conn.execute(
                        """
                        INSERT INTO document_chunks (
                            id, section_id, chunk_index, text, token_count, start_char, end_char, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            chunk.id,
                            chunk.section_id,
                            chunk.chunk_index,
                            chunk.text,
                            chunk.token_count,
                            chunk.start_char,
                            chunk.end_char,
                            chunk.created_at,
                        ),
                    )

    def has_chunks(self, document_id: str) -> bool:
        """Check whether any chunks are already persisted for the given document."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                WHERE s.document_id = ? LIMIT 1;
                """,
                (document_id,),
            ).fetchone()
            return row is not None

    def delete_chunks_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document, returning the number of deleted rows."""
        with self._get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE section_id IN (
                        SELECT id FROM document_sections WHERE document_id = ?
                    );
                    """,
                    (document_id,),
                )
                return cursor.rowcount

    def get_chunk(self, chunk_id: str) -> Optional[ChunkWithProvenance]:
        """Fetch a chunk enriched with source document and section provenance."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    c.id,
                    s.document_id,
                    c.section_id,
                    c.chunk_index,
                    c.text,
                    c.token_count,
                    c.start_char,
                    c.end_char,
                    c.created_at,
                    d.filename,
                    d.file_type,
                    d.source_path,
                    d.title AS document_title,
                    s.section_index,
                    s.section_title,
                    s.page_number
                FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                JOIN documents d ON s.document_id = d.id
                WHERE c.id = ?;
                """,
                (chunk_id,),
            ).fetchone()
            if not row:
                return None
            return ChunkWithProvenance(
                id=row["id"],
                document_id=row["document_id"],
                section_id=row["section_id"],
                chunk_index=row["chunk_index"],
                text=row["text"],
                token_count=row["token_count"],
                start_char=row["start_char"],
                end_char=row["end_char"],
                created_at=row["created_at"],
                filename=row["filename"],
                file_type=row["file_type"],
                source_path=row["source_path"],
                document_title=row["document_title"],
                section_index=row["section_index"],
                section_title=row["section_title"],
                page_number=row["page_number"],
            )

    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """Fetch all chunks for a document ordered by section and chunk index."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    s.document_id,
                    c.section_id,
                    c.chunk_index,
                    c.text,
                    c.token_count,
                    c.start_char,
                    c.end_char,
                    c.created_at
                FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                WHERE s.document_id = ?
                ORDER BY s.section_index ASC, c.chunk_index ASC;
                """,
                (document_id,),
            ).fetchall()
            return [
                DocumentChunk(
                    id=r["id"],
                    document_id=r["document_id"],
                    section_id=r["section_id"],
                    chunk_index=r["chunk_index"],
                    text=r["text"],
                    token_count=r["token_count"],
                    start_char=r["start_char"],
                    end_char=r["end_char"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def list_chunk_summaries(self, document_id: Optional[str] = None) -> List[ChunkSummary]:
        """List summary statistics of chunks grouped by document."""
        with self._get_connection() as conn:
            query = """
                SELECT
                    d.id AS document_id,
                    d.filename,
                    COUNT(c.id) AS total_chunks,
                    COALESCE(SUM(c.token_count), 0) AS total_tokens,
                    COALESCE(AVG(c.token_count), 0.0) AS avg_tokens
                FROM documents d
                JOIN document_sections s ON d.id = s.document_id
                JOIN document_chunks c ON s.id = c.section_id
            """
            params = []
            if document_id:
                query += " WHERE d.id = ?"
                params.append(document_id)
            query += " GROUP BY d.id ORDER BY d.created_at DESC;"

            rows = conn.execute(query, tuple(params)).fetchall()
            return [
                ChunkSummary(
                    document_id=r["document_id"],
                    filename=r["filename"],
                    total_chunks=r["total_chunks"],
                    total_tokens=r["total_tokens"],
                    avg_tokens=round(r["avg_tokens"], 1),
                )
                for r in rows
            ]

    def count_chunks(self, document_id: Optional[str] = None) -> int:
        """Count total chunks across corpus or for a specific document."""
        with self._get_connection() as conn:
            if document_id:
                row = conn.execute(
                    """
                    SELECT COUNT(c.id) FROM document_chunks c
                    JOIN document_sections s ON c.section_id = s.id
                    WHERE s.document_id = ?;
                    """,
                    (document_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM document_chunks;").fetchone()
            return row[0] if row else 0

    def get_corpus_stats(self) -> Dict[str, int]:
        """Return corpus aggregate counts for documents, sections, chunks, and chunk tokens."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM documents) AS total_documents,
                    (SELECT COUNT(*) FROM document_sections) AS total_sections,
                    (SELECT COUNT(*) FROM document_chunks) AS total_chunks,
                    (SELECT COALESCE(SUM(token_count), 0) FROM document_chunks) AS total_chunk_tokens;
                """
            ).fetchone()
            return {
                "total_documents": row["total_documents"],
                "total_sections": row["total_sections"],
                "total_chunks": row["total_chunks"],
                "total_chunk_tokens": row["total_chunk_tokens"],
            }

    def list_documents_with_stats(self) -> List[Dict[str, Any]]:
        """List all documents with joined section, chunk, and summed chunk-token counts."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.filename,
                    d.title,
                    d.file_type,
                    d.content_hash,
                    d.created_at,
                    COUNT(DISTINCT s.id) AS section_count,
                    COUNT(c.id) AS chunk_count,
                    COALESCE(SUM(c.token_count), 0) AS total_chunk_tokens
                FROM documents d
                LEFT JOIN document_sections s ON d.id = s.document_id
                LEFT JOIN document_chunks c ON s.id = c.section_id
                GROUP BY d.id
                ORDER BY d.created_at DESC;
                """
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "filename": r["filename"],
                    "title": r["title"],
                    "file_type": r["file_type"],
                    "content_hash": r["content_hash"],
                    "created_at": r["created_at"],
                    "section_count": r["section_count"],
                    "chunk_count": r["chunk_count"],
                    "total_chunk_tokens": r["total_chunk_tokens"],
                }
                for r in rows
            ]

    def get_document_details(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full document details, metadata, section breakdown, and chunk token summary."""
        with self._get_connection() as conn:
            doc_row = conn.execute(
                """
                SELECT id, filename, title, file_type, content_hash, metadata, created_at, updated_at
                FROM documents WHERE id = ?;
                """,
                (document_id,),
            ).fetchone()

            if not doc_row:
                return None

            section_rows = conn.execute(
                """
                SELECT id, section_index, page_number, section_title, text
                FROM document_sections
                WHERE document_id = ?
                ORDER BY section_index ASC;
                """,
                (document_id,),
            ).fetchall()

            chunk_stats = conn.execute(
                """
                SELECT COUNT(c.id) AS chunk_count, COALESCE(SUM(c.token_count), 0) AS total_chunk_tokens
                FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                WHERE s.document_id = ?;
                """,
                (document_id,),
            ).fetchone()

            metadata = json.loads(doc_row["metadata"]) if doc_row["metadata"] else {}

            sections = [
                {
                    "id": s["id"],
                    "section_index": s["section_index"],
                    "page_number": s["page_number"],
                    "section_title": s["section_title"],
                    "char_length": len(s["text"]),
                    "text_preview": s["text"][:200],
                }
                for s in section_rows
            ]

            return {
                "id": doc_row["id"],
                "filename": doc_row["filename"],
                "title": doc_row["title"],
                "file_type": doc_row["file_type"],
                "content_hash": doc_row["content_hash"],
                "created_at": doc_row["created_at"],
                "updated_at": doc_row["updated_at"],
                "metadata": metadata,
                "section_count": len(sections),
                "chunk_count": chunk_stats["chunk_count"] if chunk_stats else 0,
                "total_chunk_tokens": chunk_stats["total_chunk_tokens"] if chunk_stats else 0,
                "sections": sections,
            }

    def get_chunks_paginated(
        self, document_id: str, limit: int = 50, offset: int = 0
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """Fetch paginated chunks for a document with provenance, returning (chunks, total_count).

        Returns None if document does not exist. Returns ([], 0) if document exists but has no chunks.
        """
        with self._get_connection() as conn:
            doc_exists = conn.execute(
                "SELECT 1 FROM documents WHERE id = ?;", (document_id,)
            ).fetchone()
            if not doc_exists:
                return None

            total_row = conn.execute(
                """
                SELECT COUNT(c.id) AS total FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                WHERE s.document_id = ?;
                """,
                (document_id,),
            ).fetchone()
            total = total_row["total"] if total_row else 0

            rows = conn.execute(
                """
                SELECT
                    c.id,
                    s.document_id,
                    c.section_id,
                    c.chunk_index,
                    c.text,
                    c.token_count,
                    c.start_char,
                    c.end_char,
                    c.created_at,
                    s.section_index,
                    s.section_title,
                    s.page_number
                FROM document_chunks c
                JOIN document_sections s ON c.section_id = s.id
                WHERE s.document_id = ?
                ORDER BY s.section_index ASC, c.chunk_index ASC
                LIMIT ? OFFSET ?;
                """,
                (document_id, limit, offset),
            ).fetchall()

            items = [
                {
                    "id": r["id"],
                    "document_id": r["document_id"],
                    "section_id": r["section_id"],
                    "chunk_index": r["chunk_index"],
                    "text": r["text"],
                    "token_count": r["token_count"],
                    "start_char": r["start_char"],
                    "end_char": r["end_char"],
                    "created_at": r["created_at"],
                    "section_index": r["section_index"],
                    "section_title": r["section_title"],
                    "page_number": r["page_number"],
                }
                for r in rows
            ]

            return items, total

