"""Unit and integration tests for Corpus Explorer read-only API endpoints."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.documents import get_repository
from app.chunking.models import DocumentChunk
from app.ingestion.models import Document, DocumentSection
from app.ingestion.storage.repository import DocumentRepository
from app.main import create_app


@pytest.fixture
def test_db_path(tmp_path: Path) -> str:
    """Provide an isolated temporary SQLite database path."""
    return str(tmp_path / "test_api_corpus.db")


@pytest.fixture
def test_repo(test_db_path: str) -> DocumentRepository:
    """Create a DocumentRepository backed by the isolated temporary database."""
    return DocumentRepository(db_path=test_db_path)


@pytest.fixture
def client(test_repo: DocumentRepository) -> TestClient:
    """Create a FastAPI TestClient with the repository dependency overridden to test_repo."""
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_corpus(test_repo: DocumentRepository):
    """Seed the isolated database with two documents, sections, and chunks."""
    doc1 = Document(
        id="doc_alpha",
        filename="alpha_paper.pdf",
        title="Alpha Research Study",
        file_type="pdf",
        source_path="data/alpha_paper.pdf",
        content_hash="hash_alpha_12345",
        metadata={"author": "Team A", "page_count": 2},
        sections=[
            DocumentSection(
                document_id="doc_alpha",
                section_index=0,
                page_number=1,
                section_title="Introduction",
                text="This is section zero of document alpha. It contains introductory information." * 5,
            ),
            DocumentSection(
                document_id="doc_alpha",
                section_index=1,
                page_number=2,
                section_title="Methodology",
                text="This is section one of document alpha covering the experimental methodology." * 4,
            ),
        ],
    )
    test_repo.save_document(doc1)

    # Fetch saved section IDs for doc1
    saved_doc1 = test_repo.get_document("doc_alpha")
    sec0_id = saved_doc1.sections[0].id
    sec1_id = saved_doc1.sections[1].id

    chunks_doc1 = [
        DocumentChunk(
            id=f"chunk_{sec0_id}_0",
            document_id="doc_alpha",
            section_id=sec0_id,
            chunk_index=0,
            text=saved_doc1.sections[0].text[0:150],
            token_count=35,
            start_char=0,
            end_char=150,
        ),
        DocumentChunk(
            id=f"chunk_{sec0_id}_1",
            document_id="doc_alpha",
            section_id=sec0_id,
            chunk_index=1,
            text=saved_doc1.sections[0].text[100:250],
            token_count=35,
            start_char=100,
            end_char=250,
        ),
        DocumentChunk(
            id=f"chunk_{sec1_id}_0",
            document_id="doc_alpha",
            section_id=sec1_id,
            chunk_index=0,
            text=saved_doc1.sections[1].text[0:200],
            token_count=45,
            start_char=0,
            end_char=200,
        ),
    ]
    test_repo.save_chunks_for_document("doc_alpha", chunks_doc1)

    # Document 2: Has sections but NO chunks
    doc2 = Document(
        id="doc_beta",
        filename="beta_notes.md",
        title="Beta Notes",
        file_type="md",
        source_path="data/beta_notes.md",
        content_hash="hash_beta_67890",
        metadata={"tags": ["notes", "scratch"]},
        sections=[
            DocumentSection(
                document_id="doc_beta",
                section_index=0,
                page_number=None,
                section_title="Overview",
                text="Raw notes in markdown without any generated chunks.",
            ),
        ],
    )
    test_repo.save_document(doc2)

    return {
        "doc1": doc1,
        "doc2": doc2,
        "chunks_doc1": chunks_doc1,
    }


def test_get_stats_empty_database(client: TestClient):
    """Stats endpoint returns zeros when the database contains no documents."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "total_documents": 0,
        "total_sections": 0,
        "total_chunks": 0,
        "total_chunk_tokens": 0,
    }


def test_list_documents_empty_database(client: TestClient):
    """Document list endpoint returns an empty list when no documents exist."""
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_get_stats_populated(client: TestClient, sample_corpus):
    """Stats endpoint correctly aggregates documents, sections, chunks, and token sums."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    # 2 documents, 3 sections (2 for doc1 + 1 for doc2), 3 chunks (all in doc1)
    # Total chunk tokens: 35 + 35 + 45 = 115
    assert data["total_documents"] == 2
    assert data["total_sections"] == 3
    assert data["total_chunks"] == 3
    assert data["total_chunk_tokens"] == 115


def test_list_documents_populated(client: TestClient, sample_corpus):
    """Document list returns aggregated counts per document without exposing source_path."""
    response = client.get("/api/documents")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2

    by_id = {item["id"]: item for item in items}
    alpha = by_id["doc_alpha"]
    assert alpha["filename"] == "alpha_paper.pdf"
    assert alpha["file_type"] == "pdf"
    assert alpha["section_count"] == 2
    assert alpha["chunk_count"] == 3
    assert alpha["total_chunk_tokens"] == 115
    assert "source_path" not in alpha

    beta = by_id["doc_beta"]
    assert beta["filename"] == "beta_notes.md"
    assert beta["section_count"] == 1
    assert beta["chunk_count"] == 0
    assert beta["total_chunk_tokens"] == 0
    assert "source_path" not in beta


def test_get_document_detail_success(client: TestClient, sample_corpus):
    """Document detail returns metadata, section summaries with previews, and chunk totals."""
    response = client.get("/api/documents/doc_alpha")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "doc_alpha"
    assert data["filename"] == "alpha_paper.pdf"
    assert data["title"] == "Alpha Research Study"
    assert data["metadata"] == {"author": "Team A", "page_count": 2}
    assert "updated_at" in data
    assert data["section_count"] == 2
    assert data["chunk_count"] == 3
    assert data["total_chunk_tokens"] == 115
    assert "source_path" not in data

    sections = data["sections"]
    assert len(sections) == 2
    assert sections[0]["section_index"] == 0
    assert sections[0]["page_number"] == 1
    assert sections[0]["section_title"] == "Introduction"
    assert len(sections[0]["text_preview"]) <= 200
    assert sections[0]["char_length"] > len(sections[0]["text_preview"])


def test_get_document_detail_not_found(client: TestClient):
    """Document detail returns 404 for a nonexistent document ID."""
    response = client.get("/api/documents/non_existent_doc_id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_get_document_chunks_success(client: TestClient, sample_corpus):
    """Document chunks endpoint returns paginated chunks with section-relative offsets."""
    response = client.get("/api/documents/doc_alpha/chunks?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2

    first_chunk = data["items"][0]
    assert first_chunk["document_id"] == "doc_alpha"
    assert first_chunk["chunk_index"] == 0
    assert first_chunk["start_char"] == 0
    assert first_chunk["end_char"] == 150
    assert first_chunk["token_count"] == 35
    assert first_chunk["section_title"] == "Introduction"
    assert first_chunk["page_number"] == 1
    assert len(first_chunk["text"]) == 150

    # Second page
    response_p2 = client.get("/api/documents/doc_alpha/chunks?limit=2&offset=2")
    assert response_p2.status_code == 200
    data_p2 = response_p2.json()
    assert len(data_p2["items"]) == 1
    third_chunk = data_p2["items"][0]
    assert third_chunk["section_title"] == "Methodology"
    assert third_chunk["page_number"] == 2


def test_get_document_chunks_empty_for_unchunked_doc(client: TestClient, sample_corpus):
    """Document with no chunks returns 200 with total=0 and items=[]."""
    response = client.get("/api/documents/doc_beta/chunks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_document_chunks_not_found(client: TestClient):
    """Document chunks returns 404 if the document itself does not exist."""
    response = client.get("/api/documents/non_existent_doc/chunks")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_get_document_chunks_validation(client: TestClient, sample_corpus):
    """Invalid pagination limits or negative offsets trigger validation error 422."""
    response_zero_limit = client.get("/api/documents/doc_alpha/chunks?limit=0")
    assert response_zero_limit.status_code == 422

    response_huge_limit = client.get("/api/documents/doc_alpha/chunks?limit=101")
    assert response_huge_limit.status_code == 422

    response_negative_offset = client.get("/api/documents/doc_alpha/chunks?offset=-1")
    assert response_negative_offset.status_code == 422
