"""Canonical document representations and ingestion data transfer models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


def generate_document_id(content_hash: str) -> str:
    """Generate a deterministic, content-addressable document identifier.

    Uses UUIDv5 derived from the SHA-256 content hash in the DNS namespace.
    Ensures identical file content yields identical stable identifiers regardless
    of local machine or ingestion environment.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"doc:{content_hash}"))


class DocumentSection(BaseModel):
    """Represents a discrete structural section or page within a canonical document."""

    id: Optional[int] = None
    document_id: str
    section_index: int = Field(..., ge=0, description="0-indexed sequence position")
    page_number: Optional[int] = Field(None, ge=1, description="1-indexed physical page number")
    section_title: Optional[str] = Field(None, description="Heading title or structural marker")
    text: str = Field(..., description="Normalized section content")


class Document(BaseModel):
    """Canonical representation of an ingested document."""

    id: str = Field(..., description="Deterministic document identifier")
    filename: str = Field(..., description="Base filename with extension")
    title: Optional[str] = Field(None, description="Extracted document title")
    file_type: str = Field(..., description="Normalized file format: pdf, docx, md, txt")
    source_path: str = Field(..., description="Normalized path relative to corpus root")
    content_hash: str = Field(..., description="SHA-256 hex digest of source file bytes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extracted metadata")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC update timestamp",
    )
    sections: List[DocumentSection] = Field(default_factory=list, description="Ordered sections")


class DocumentSummary(BaseModel):
    """Lightweight document overview for listings."""

    id: str
    filename: str
    title: Optional[str]
    file_type: str
    source_path: str
    content_hash: str
    section_count: int
    created_at: str


class IngestionItemResult(BaseModel):
    """Outcome for a single ingested file."""

    file_path: str
    status: str  # "ingested" | "skipped" | "replaced" | "failed"
    document_id: Optional[str] = None
    error: Optional[str] = None


class IngestionResult(BaseModel):
    """Summary of batch or single-file ingestion execution."""

    total_discovered: int = 0
    ingested: int = 0
    skipped: int = 0
    replaced: int = 0
    failed: int = 0
    items: List[IngestionItemResult] = Field(default_factory=list)
