"""Comprehensive tests for document ingestion, normalization, and persistence."""

from pathlib import Path
import sqlite3
import pytest
from app.ingestion.models import Document, DocumentSection, generate_document_id
from app.ingestion.normalizer import normalize_text
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.txt_parser import TxtParser
from app.ingestion.service import DocumentIngestionService
from app.ingestion.storage.repository import DocumentRepository


# ---------------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_text_line_endings():
    raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
    result = normalize_text(raw)
    assert result == "Line 1\nLine 2\nLine 3\nLine 4"


def test_normalize_text_preserves_indentation_and_code():
    raw = "def foo():\n    x = 1\n\treturn x\n"
    result = normalize_text(raw)
    assert "    x = 1" in result
    assert "\treturn x" in result


def test_normalize_text_collapses_excessive_newlines():
    raw = "Paragraph 1\n\n\n\n\nParagraph 2"
    result = normalize_text(raw)
    assert result == "Paragraph 1\n\nParagraph 2"


def test_normalize_text_strips_control_characters():
    raw = "Text with \x00null and \x07bell chars."
    result = normalize_text(raw)
    assert result == "Text with null and bell chars."


def test_normalize_text_preserves_unicode_and_symbols():
    raw = "Equations: ∀x ∈ ℝ, ∑x² ≥ 0. Quotes: “Adaptive RAG” — German: Grüße."
    result = normalize_text(raw)
    assert "∀x ∈ ℝ" in result
    assert "“Adaptive RAG”" in result
    assert "Grüße" in result


# ---------------------------------------------------------------------------
# Parser-Specific Tests
# ---------------------------------------------------------------------------


def test_txt_parser_utf8(fixtures_dir: Path):
    parser = TxtParser()
    file_path = fixtures_dir / "sample.txt"
    doc = parser.parse(file_path, "sample.txt", "mockhash1")

    assert doc.file_type == "txt"
    assert len(doc.sections) == 1
    assert doc.sections[0].page_number is None
    assert doc.sections[0].section_index == 0
    assert "Agentic RAG Architecture" in doc.sections[0].text
    assert doc.metadata["encoding"] == "utf-8"


def test_txt_parser_cp1252_fallback(fixtures_dir: Path):
    parser = TxtParser()
    file_path = fixtures_dir / "cp1252_sample.txt"
    doc = parser.parse(file_path, "cp1252_sample.txt", "mockhash2")

    assert doc.file_type == "txt"
    assert doc.metadata["encoding"] == "cp1252"
    assert "Adaptive Retrieval Systems" in doc.sections[0].text


def test_txt_parser_undecodable_error(tmp_path: Path):
    parser = TxtParser()
    bad_file = tmp_path / "bad.txt"
    # CP1252 rejects 0x81, 0x8D, 0x8F, 0x90, 0x9D in strict byte decoding
    bad_file.write_bytes(b"\x81\x8d\x8f\x90\x9d")
    with pytest.raises(ValueError, match="Failed to decode text file"):
        parser.parse(bad_file, "bad.txt", "badhash")


def test_markdown_parser_heading_preservation(fixtures_dir: Path):
    parser = MarkdownParser()
    file_path = fixtures_dir / "sample.md"
    doc = parser.parse(file_path, "sample.md", "mockhash3")

    assert doc.file_type == "md"
    assert doc.title == "Agentic RAG Overview"
    # Verify section headings are preserved
    headings = [s.section_title for s in doc.sections]
    assert "Agentic RAG Overview" in headings
    assert "System Architecture" in headings
    assert "Ingestion Subsystem" in headings
    assert "Verification and Self-Correction" in headings

    # Verify section texts
    sec_arch = next(s for s in doc.sections if s.section_title == "System Architecture")
    assert "adaptive loop controllers" in sec_arch.text


def test_docx_parser_heading_preservation(fixtures_dir: Path):
    parser = DocxParser()
    file_path = fixtures_dir / "sample.docx"
    doc = parser.parse(file_path, "sample.docx", "mockhash4")

    assert doc.file_type == "docx"
    assert doc.metadata.get("author") == "System Researcher"
    assert len(doc.sections) >= 3

    headings = [s.section_title for s in doc.sections if s.section_title]
    assert "Agentic RAG Design" in headings
    assert "Adaptive Retrieval Planning" in headings
    assert "Fact Verification" in headings


def test_pdf_parser_page_preservation(fixtures_dir: Path):
    parser = PdfParser()
    file_path = fixtures_dir / "sample.pdf"
    doc = parser.parse(file_path, "sample.pdf", "mockhash5")

    assert doc.file_type == "pdf"
    assert doc.title == "Agentic RAG Paper"
    assert doc.metadata.get("author") == "Lead Researcher"
    assert len(doc.sections) == 2

    # Check page numbers are preserved
    assert doc.sections[0].page_number == 1
    assert doc.sections[1].page_number == 2
    assert "Section 1: Agentic RAG System Introduction" in doc.sections[0].text
    assert "Section 2: Adaptive Planning and Verification" in doc.sections[1].text


# ---------------------------------------------------------------------------
# Canonical Representation & Deterministic Identity
# ---------------------------------------------------------------------------


def test_deterministic_document_id():
    hash1 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    id1 = generate_document_id(hash1)
    id2 = generate_document_id(hash1)
    assert id1 == id2
    assert isinstance(id1, str)
    assert len(id1) == 36  # Standard UUID string representation


# ---------------------------------------------------------------------------
# Storage & Persistence Tests
# ---------------------------------------------------------------------------


def test_sqlite_persistence_and_retrieval(repo: DocumentRepository, fixtures_dir: Path):
    parser = MarkdownParser()
    file_path = fixtures_dir / "sample.md"
    doc = parser.parse(file_path, "sample.md", "hash_md_persist")

    saved = repo.save_document(doc)
    assert saved is True

    # Retrieve and verify all fields survive roundtrip
    retrieved = repo.get_document(doc.id)
    assert retrieved is not None
    assert retrieved.id == doc.id
    assert retrieved.filename == doc.filename
    assert retrieved.title == doc.title
    assert retrieved.file_type == "md"
    assert retrieved.content_hash == "hash_md_persist"
    assert retrieved.metadata["headings"] == doc.metadata["headings"]
    assert len(retrieved.sections) == len(doc.sections)

    for orig_sec, ret_sec in zip(doc.sections, retrieved.sections):
        assert ret_sec.section_index == orig_sec.section_index
        assert ret_sec.section_title == orig_sec.section_title
        assert ret_sec.text == orig_sec.text


def test_sqlite_foreign_keys_and_cascade(repo: DocumentRepository):
    # Verify foreign key pragma is active
    with repo._get_connection() as conn:
        fk_on = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_on == 1

    doc = Document(
        id="doc_fk_test",
        filename="fk.txt",
        file_type="txt",
        source_path="fk.txt",
        content_hash="fkhash123",
        sections=[
            DocumentSection(document_id="doc_fk_test", section_index=0, text="Section 0 text"),
            DocumentSection(document_id="doc_fk_test", section_index=1, text="Section 1 text"),
        ],
    )
    repo.save_document(doc)

    # Verify sections exist
    with repo._get_connection() as conn:
        sec_count = conn.execute(
            "SELECT COUNT(*) FROM document_sections WHERE document_id = ?", ("doc_fk_test",)
        ).fetchone()[0]
        assert sec_count == 2

    # Delete parent document and verify cascade delete
    deleted = repo.delete_document("doc_fk_test")
    assert deleted is True

    with repo._get_connection() as conn:
        sec_count_after = conn.execute(
            "SELECT COUNT(*) FROM document_sections WHERE document_id = ?", ("doc_fk_test",)
        ).fetchone()[0]
        assert sec_count_after == 0


def test_sqlite_section_uniqueness_constraint(repo: DocumentRepository):
    doc = Document(
        id="doc_unique_test",
        filename="u.txt",
        file_type="txt",
        source_path="u.txt",
        content_hash="uhash123",
        sections=[
            DocumentSection(document_id="doc_unique_test", section_index=0, text="First"),
            DocumentSection(document_id="doc_unique_test", section_index=0, text="Duplicate index"),
        ],
    )
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_document(doc)


# ---------------------------------------------------------------------------
# Duplicate Policy Tests
# ---------------------------------------------------------------------------


def test_duplicate_skip_policy(service: DocumentIngestionService, fixtures_dir: Path):
    file_path = fixtures_dir / "sample.txt"

    res1 = service.ingest_file(file_path, on_duplicate="skip")
    assert res1.status == "ingested"

    # Ingesting the same file again with skip policy
    res2 = service.ingest_file(file_path, on_duplicate="skip")
    assert res2.status == "skipped"
    assert res2.document_id == res1.document_id

    # Verify original document remains unchanged
    doc = service.repository.get_document(res1.document_id)
    assert doc is not None


def test_duplicate_replace_policy(service: DocumentIngestionService, fixtures_dir: Path):
    file_path = fixtures_dir / "sample.txt"

    res1 = service.ingest_file(file_path, on_duplicate="skip")
    assert res1.status == "ingested"

    # Re-ingest with replace policy
    res2 = service.ingest_file(file_path, on_duplicate="replace")
    assert res2.status == "replaced"
    assert res2.document_id == res1.document_id

    # Verify document is still intact in storage
    doc = service.repository.get_document(res1.document_id)
    assert doc is not None
    assert len(doc.sections) == 1


# ---------------------------------------------------------------------------
# Error Handling & Batch Ingestion Tests
# ---------------------------------------------------------------------------


def test_ingest_empty_file(service: DocumentIngestionService, fixtures_dir: Path):
    empty_file = fixtures_dir / "empty.txt"
    res = service.ingest_file(empty_file)
    assert res.status == "failed"
    assert "empty" in res.error.lower()


def test_ingest_corrupt_file(service: DocumentIngestionService, fixtures_dir: Path):
    corrupt_file = fixtures_dir / "corrupt.pdf"
    res = service.ingest_file(corrupt_file)
    assert res.status == "failed"
    assert "corrupt" in res.error.lower() or "unreadable" in res.error.lower()


def test_ingest_unsupported_file(service: DocumentIngestionService, fixtures_dir: Path):
    unsupported = fixtures_dir / "unsupported.xyz"
    res = service.ingest_file(unsupported)
    assert res.status == "failed"
    assert "unsupported" in res.error.lower()


def test_ingest_missing_file(service: DocumentIngestionService, fixtures_dir: Path):
    missing = fixtures_dir / "non_existent_file.pdf"
    res = service.ingest_file(missing)
    assert res.status == "failed"
    assert "not found" in res.error.lower()


def test_batch_ingestion_resilience(service: DocumentIngestionService, fixtures_dir: Path):
    """Batch ingestion should continue past invalid/corrupt files and record counts."""
    result = service.ingest_directory(fixtures_dir, on_duplicate="skip")

    # Fixtures directory contains:
    # 4 valid files (sample.txt, cp1252_sample.txt, sample.md, sample.docx, sample.pdf) -> total 5 valid supported
    # 2 invalid files (empty.txt, corrupt.pdf)
    # 1 unsupported file (unsupported.xyz) is excluded from discovered candidates
    assert result.total_discovered >= 7
    assert result.ingested >= 4
    assert result.failed >= 2  # empty.txt and corrupt.pdf fail cleanly without crashing batch

    # Check that listings reflect the successfully ingested documents
    summaries = service.repository.list_documents()
    assert len(summaries) == result.ingested
