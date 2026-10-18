"""Pydantic schemas for the read-only Corpus Explorer API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CorpusStatsResponse(BaseModel):
    """Corpus aggregate statistics."""

    total_documents: int = Field(..., ge=0, description="Total number of stored canonical documents")
    total_sections: int = Field(..., ge=0, description="Total number of structural document sections")
    total_chunks: int = Field(..., ge=0, description="Total number of generated chunks")
    total_chunk_tokens: int = Field(
        ...,
        ge=0,
        description="Sum of token counts across all stored chunks (includes overlapping tokens)",
    )


class DocumentListItem(BaseModel):
    """Summary item for the document catalog."""

    id: str
    filename: str
    title: Optional[str] = None
    file_type: str
    content_hash: str
    created_at: str
    section_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    total_chunk_tokens: int = Field(..., ge=0, description="Summed chunk tokens for this document")


class SectionSummaryItem(BaseModel):
    """Section summary with preview snippet for document detail view."""

    id: int
    section_index: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    char_length: int
    text_preview: str = Field(..., description="Up to 200 character preview of section text")


class DocumentDetailResponse(BaseModel):
    """Comprehensive document details, metadata, and ordered sections."""

    id: str
    filename: str
    title: Optional[str] = None
    file_type: str
    content_hash: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    section_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    total_chunk_tokens: int = Field(..., ge=0)
    sections: List[SectionSummaryItem] = Field(default_factory=list)


class ChunkItem(BaseModel):
    """A single document chunk with provenance and exact section-relative offsets."""

    id: str
    document_id: str
    section_id: int
    chunk_index: int
    text: str
    token_count: int
    start_char: int = Field(..., ge=0, description="0-indexed inclusive start offset in section.text")
    end_char: int = Field(..., ge=0, description="0-indexed exclusive end offset in section.text")
    created_at: str
    section_index: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None


class PaginatedChunksResponse(BaseModel):
    """Paginated collection of chunks belonging to a document."""

    total: int = Field(..., ge=0, description="Total chunks for this document")
    limit: int = Field(..., ge=1, description="Requested page limit")
    offset: int = Field(..., ge=0, description="Requested page offset")
    items: List[ChunkItem] = Field(default_factory=list)
