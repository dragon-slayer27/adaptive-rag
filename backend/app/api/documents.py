"""Read-only API endpoints for the Corpus Explorer."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import (
    ChunkItem,
    CorpusStatsResponse,
    DocumentDetailResponse,
    DocumentListItem,
    PaginatedChunksResponse,
)
from app.core.config import get_settings
from app.ingestion.storage.repository import DocumentRepository

router = APIRouter()


def get_repository() -> DocumentRepository:
    """Dependency provider for DocumentRepository."""
    settings = get_settings()
    return DocumentRepository(db_path=settings.corpus_db_path)


@router.get("/stats", response_model=CorpusStatsResponse)
def get_stats(repo: DocumentRepository = Depends(get_repository)) -> CorpusStatsResponse:
    """Get corpus-wide aggregate counts for documents, sections, chunks, and chunk tokens."""
    stats = repo.get_corpus_stats()
    return CorpusStatsResponse(**stats)


@router.get("/documents", response_model=List[DocumentListItem])
def list_documents(repo: DocumentRepository = Depends(get_repository)) -> List[DocumentListItem]:
    """List all stored documents with joined section, chunk, and chunk-token aggregates."""
    docs = repo.list_documents_with_stats()
    return [DocumentListItem(**d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    repo: DocumentRepository = Depends(get_repository),
) -> DocumentDetailResponse:
    """Get document details, metadata, and ordered sections with text previews."""
    doc = repo.get_document_details(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetailResponse(**doc)


@router.get("/documents/{document_id}/chunks", response_model=PaginatedChunksResponse)
def get_document_chunks(
    document_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page limit between 1 and 100"),
    offset: int = Query(0, ge=0, description="Page offset"),
    repo: DocumentRepository = Depends(get_repository),
) -> PaginatedChunksResponse:
    """Get paginated chunks for a document, with exact section-relative offsets and provenance."""
    result = repo.get_chunks_paginated(document_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    items, total = result
    return PaginatedChunksResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[ChunkItem(**item) for item in items],
    )
