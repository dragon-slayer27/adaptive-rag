"""Data models for document chunks, provenance, and batch chunking results."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


def generate_chunk_id(section_id: int, chunk_index: int) -> str:
    """Generate deterministic chunk identifier derived from parent section and sequence index."""
    return f"chunk_{section_id}_{chunk_index}"


class DocumentChunk(BaseModel):
    """Canonical model for a single chunk of text within a document section."""

    id: str = Field(..., description="Deterministic chunk identifier")
    document_id: str = Field(..., description="Parent document identifier (derived from section)")
    section_id: int = Field(..., description="Source section database identifier")
    chunk_index: int = Field(..., ge=0, description="0-indexed order within section")
    text: str = Field(..., description="Exact substring of section text")
    token_count: int = Field(..., ge=0, description="Evaluated token count")
    start_char: int = Field(..., ge=0, description="0-indexed inclusive start offset in section.text")
    end_char: int = Field(..., ge=0, description="0-indexed exclusive end offset in section.text")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp",
    )


class ChunkWithProvenance(BaseModel):
    """Chunk enriched with joined source document and section provenance."""

    id: str
    document_id: str
    section_id: int
    chunk_index: int
    text: str
    token_count: int
    start_char: int
    end_char: int
    created_at: str
    # Joined Document provenance
    filename: str
    file_type: str
    source_path: str
    document_title: Optional[str] = None
    # Joined Section provenance
    section_index: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None


class ChunkSummary(BaseModel):
    """Aggregated chunking statistics for a document."""

    document_id: str
    filename: str
    total_chunks: int
    total_tokens: int
    avg_tokens: float


class DocumentChunkingResult(BaseModel):
    """Result of chunking a single document."""

    document_id: str
    filename: str
    status: str  # "chunked" | "skipped" | "rebuilt" | "failed"
    chunks_created: int = 0
    error: Optional[str] = None


class BatchChunkingResult(BaseModel):
    """Summary of batch chunking execution."""

    total_documents: int = 0
    chunked: int = 0
    skipped: int = 0
    rebuilt: int = 0
    failed: int = 0
    total_chunks_created: int = 0
    results: List[DocumentChunkingResult] = Field(default_factory=list)
