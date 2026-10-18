"""Document chunking service orchestrating splitting, persistence, and batch processing."""

from typing import List, Optional
from app.chunking.models import (
    BatchChunkingResult,
    DocumentChunk,
    DocumentChunkingResult,
)
from app.chunking.splitter import SectionChunker
from app.chunking.tokenizer import BaseTokenizer, TiktokenTokenizer
from app.core.config import get_settings
from app.ingestion.storage.repository import DocumentRepository


class ChunkingService:
    """Orchestrates section-aware document chunking and transactional SQLite storage."""

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        tokenizer: Optional[BaseTokenizer] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or DocumentRepository()
        self.tokenizer = tokenizer or TiktokenTokenizer(encoding_name=settings.tokenizer_encoding)
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        self.chunker = SectionChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def chunk_document(
        self,
        document_id: str,
        rebuild: bool = False,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> DocumentChunkingResult:
        """Chunk all sections of a single document.

        Args:
            document_id: Database document identifier.
            rebuild: If True, atomically deletes and replaces existing chunks.
            chunk_size: Optional override for chunk token capacity.
            chunk_overlap: Optional override for chunk token overlap.

        Returns:
            DocumentChunkingResult tracking status and chunk counts.
        """
        doc = self.repository.get_document(document_id)
        if not doc:
            return DocumentChunkingResult(
                document_id=document_id,
                filename="unknown",
                status="failed",
                error=f"Document not found: {document_id}",
            )

        already_chunked = self.repository.has_chunks(document_id)
        if already_chunked and not rebuild:
            return DocumentChunkingResult(
                document_id=doc.id,
                filename=doc.filename,
                status="skipped",
                chunks_created=0,
            )

        # Allow per-run parameter overrides
        effective_size = chunk_size or self.chunk_size
        effective_overlap = self.chunk_overlap if chunk_overlap is None else chunk_overlap
        chunker = (
            self.chunker
            if (effective_size == self.chunk_size and effective_overlap == self.chunk_overlap)
            else SectionChunker(
                tokenizer=self.tokenizer,
                chunk_size=effective_size,
                chunk_overlap=effective_overlap,
            )
        )

        all_chunks: List[DocumentChunk] = []

        try:
            for section in doc.sections:
                if section.id is None:
                    raise ValueError(
                        f"Section {section.section_index} of document {doc.id} has no database ID"
                    )

                if not section.text or not section.text.strip():
                    continue

                section_chunks = chunker.chunk_section(
                    text=section.text,
                    document_id=doc.id,
                    section_id=section.id,
                )
                all_chunks.extend(section_chunks)

            # Atomically save chunks in a single transaction
            self.repository.save_chunks_for_document(doc.id, all_chunks)

            status = "rebuilt" if already_chunked else "chunked"
            return DocumentChunkingResult(
                document_id=doc.id,
                filename=doc.filename,
                status=status,
                chunks_created=len(all_chunks),
            )

        except Exception as exc:
            return DocumentChunkingResult(
                document_id=doc.id,
                filename=doc.filename,
                status="failed",
                error=str(exc),
            )

    def chunk_all(
        self,
        rebuild: bool = False,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> BatchChunkingResult:
        """Process all documents in the corpus.

        Fault-tolerant: each document is processed in its own transaction so that
        an error on one document does not prevent the remaining documents from chunking.
        """
        docs = self.repository.list_documents()
        batch_result = BatchChunkingResult(total_documents=len(docs))

        for doc_summary in docs:
            res = self.chunk_document(
                document_id=doc_summary.id,
                rebuild=rebuild,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            batch_result.results.append(res)

            if res.status == "chunked":
                batch_result.chunked += 1
                batch_result.total_chunks_created += res.chunks_created
            elif res.status == "rebuilt":
                batch_result.rebuilt += 1
                batch_result.total_chunks_created += res.chunks_created
            elif res.status == "skipped":
                batch_result.skipped += 1
            elif res.status == "failed":
                batch_result.failed += 1

        return batch_result
