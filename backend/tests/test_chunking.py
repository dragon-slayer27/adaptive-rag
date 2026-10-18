"""Comprehensive tests for document chunking, tokenizer abstraction, and chunk storage."""

from pathlib import Path
import sqlite3
import pytest
from app.chunking.models import DocumentChunk, generate_chunk_id
from app.chunking.service import ChunkingService
from app.chunking.splitter import SectionChunker
from app.chunking.tokenizer import CharacterTokenizer, TiktokenTokenizer
from app.ingestion.models import Document, DocumentSection
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.storage.repository import DocumentRepository


@pytest.fixture
def tokenizer() -> TiktokenTokenizer:
    return TiktokenTokenizer(encoding_name="cl100k_base")


@pytest.fixture
def chunker(tokenizer: TiktokenTokenizer) -> SectionChunker:
    return SectionChunker(tokenizer=tokenizer, chunk_size=50, chunk_overlap=10)


@pytest.fixture
def populated_repo(repo: DocumentRepository, fixtures_dir: Path) -> DocumentRepository:
    """Repository pre-populated with parsed synthetic fixtures."""
    pdf_parser = PdfParser()
    doc = pdf_parser.parse(fixtures_dir / "sample.pdf", "sample.pdf", "pdf_hash_for_chunking")
    repo.save_document(doc)
    return repo


# ---------------------------------------------------------------------------
# Tokenizer Tests
# ---------------------------------------------------------------------------


def test_tiktoken_tokenizer_counts(tokenizer: TiktokenTokenizer):
    text = "Hello world! Agentic RAG system."
    tokens = tokenizer.encode(text)
    assert len(tokens) == tokenizer.count_tokens(text)
    assert tokenizer.decode(tokens) == text


def test_character_tokenizer():
    char_tok = CharacterTokenizer()
    text = "abc 123"
    assert char_tok.count_tokens(text) == 7
    encoded = char_tok.encode(text)
    assert char_tok.decode(encoded) == text


def test_tokenizer_invalid_encoding():
    with pytest.raises(ValueError, match="Unknown or invalid tiktoken encoding"):
        TiktokenTokenizer(encoding_name="non_existent_encoding_xyz")


# ---------------------------------------------------------------------------
# SectionChunker: Sizing, Overlap, and Boundary Tests
# ---------------------------------------------------------------------------


def test_short_section_produces_single_chunk(chunker: SectionChunker):
    text = "Short text under 50 tokens."
    chunks = chunker.chunk_section(text=text, document_id="doc1", section_id=1)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_index == 0
    assert chunk.text == text
    assert chunk.start_char == 0
    assert chunk.end_char == len(text)
    assert text[chunk.start_char : chunk.end_char] == chunk.text


def test_empty_and_whitespace_only_sections(chunker: SectionChunker):
    assert chunker.chunk_section("", document_id="doc1", section_id=1) == []
    assert chunker.chunk_section("   \n\t  \n", document_id="doc1", section_id=1) == []


def test_exact_chunk_size_boundary(tokenizer: TiktokenTokenizer):
    # Construct text with exactly 20 tokens
    words = ["word"] * 20
    text = " ".join(words)
    tok_count = tokenizer.count_tokens(text)

    exact_chunker = SectionChunker(tokenizer=tokenizer, chunk_size=tok_count, chunk_overlap=5)
    chunks = exact_chunker.chunk_section(text=text, document_id="doc1", section_id=1)
    assert len(chunks) == 1
    assert chunks[0].text == text

    # Now add one more token: must produce 2 chunks
    plus_one_text = text + " extra"
    assert tokenizer.count_tokens(plus_one_text) > tok_count
    chunks_plus = exact_chunker.chunk_section(text=plus_one_text, document_id="doc1", section_id=1)
    assert len(chunks_plus) == 2


def test_multi_chunk_section_with_overlap(chunker: SectionChunker):
    # Create longer text requiring multiple chunks with chunk_size=50
    paragraphs = [
        f"Paragraph {i}: The adaptive retrieval controller evaluates information needs dynamically."
        for i in range(15)
    ]
    text = "\n\n".join(paragraphs)

    chunks = chunker.chunk_section(text=text, document_id="doc1", section_id=1)
    assert len(chunks) >= 3

    for idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == idx
        assert chunk.token_count <= 50
        assert text[chunk.start_char : chunk.end_char] == chunk.text

        # Verify strict forward progress
        if idx > 0:
            prev_chunk = chunks[idx - 1]
            assert chunk.start_char > prev_chunk.start_char
            assert chunk.start_char < prev_chunk.end_char  # indicates overlap exists


def test_chunker_invalid_parameters(tokenizer: TiktokenTokenizer):
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        SectionChunker(tokenizer=tokenizer, chunk_size=0, chunk_overlap=0)

    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        SectionChunker(tokenizer=tokenizer, chunk_size=100, chunk_overlap=-1)

    with pytest.raises(ValueError, match="strictly less than chunk_size"):
        SectionChunker(tokenizer=tokenizer, chunk_size=100, chunk_overlap=100)


# ---------------------------------------------------------------------------
# Unicode & Offset Invariant Tests
# ---------------------------------------------------------------------------


def test_unicode_multi_byte_offset_invariant(tokenizer: TiktokenTokenizer):
    """Verify that multi-byte UTF-8 characters (emojis, CJK, accents, math symbols)
    strictly satisfy text[start_char:end_char] == chunk.text without splitting code points.
    """
    complex_unicode = (
        "Artificial Intelligence & Agentic RAG: 人工智能系统与自适应检索。\n"
        "Mathematical expressions: ∀x ∈ ℝ, ∃y s.t. f(x, y) = ∫ exp(-t²) dt ≥ 0.\n"
        "International text: Résumé des systèmes d'information, Grüße aus München, café crème.\n"
        "Emojis & symbols: 🚀 🔍 🧠 ⚡ 🤖 📊 🎯 ✨.\n"
        "Complex combining characters: Z͑aͧlͫgͬoͮ text and diacritics.\n"
    ) * 4

    unicode_chunker = SectionChunker(tokenizer=tokenizer, chunk_size=40, chunk_overlap=10)
    chunks = unicode_chunker.chunk_section(text=complex_unicode, document_id="doc_uni", section_id=42)

    assert len(chunks) >= 4
    for chunk in chunks:
        # Strict invariant test
        slice_result = complex_unicode[chunk.start_char : chunk.end_char]
        assert slice_result == chunk.text, "Chunk text must exactly match section slice"
        assert tokenizer.count_tokens(chunk.text) <= 40
        assert chunk.token_count == tokenizer.count_tokens(chunk.text)


def test_code_and_indentation_preservation(tokenizer: TiktokenTokenizer):
    code_text = (
        "def compute_score(query: str, doc_tokens: list) -> float:\n"
        "    score = 0.0\n"
        "    for tok in doc_tokens:\n"
        "        if tok in query:\n"
        "            score += 1.0\n"
        "\treturn score\n"
    ) * 5

    code_chunker = SectionChunker(tokenizer=tokenizer, chunk_size=35, chunk_overlap=8)
    chunks = code_chunker.chunk_section(text=code_text, document_id="doc_code", section_id=99)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert code_text[chunk.start_char : chunk.end_char] == chunk.text
        # Tabs and indentation preserved intact
        if "    score = 0.0" in chunk.text:
            assert "    score = 0.0" in code_text[chunk.start_char : chunk.end_char]


# ---------------------------------------------------------------------------
# Section and Page Boundary Isolation Tests
# ---------------------------------------------------------------------------


def test_section_and_page_boundary_isolation(populated_repo: DocumentRepository):
    """Ensure chunking operates per section and NEVER crosses page or section boundaries."""
    doc = populated_repo.list_documents()[0]
    full_doc = populated_repo.get_document(doc.id)
    assert len(full_doc.sections) == 2  # Multi-page PDF fixture

    service = ChunkingService(repository=populated_repo, chunk_size=20, chunk_overlap=5)
    res = service.chunk_document(doc.id)
    assert res.status == "chunked"
    assert res.chunks_created > 0

    chunks = populated_repo.get_chunks_by_document(doc.id)

    # Chunks for Page 1
    page1_section_id = full_doc.sections[0].id
    page1_chunks = [c for c in chunks if c.section_id == page1_section_id]
    assert len(page1_chunks) >= 1
    for c in page1_chunks:
        assert full_doc.sections[0].text[c.start_char : c.end_char] == c.text
        # Must not contain text from Page 2
        assert "Section 2" not in c.text

    # Chunks for Page 2
    page2_section_id = full_doc.sections[1].id
    page2_chunks = [c for c in chunks if c.section_id == page2_section_id]
    assert len(page2_chunks) >= 1
    for c in page2_chunks:
        assert full_doc.sections[1].text[c.start_char : c.end_char] == c.text
        # Must not contain text from Page 1
        assert "Section 1" not in c.text


# ---------------------------------------------------------------------------
# SQLite Persistence, Foreign Keys & Schema Integrity
# ---------------------------------------------------------------------------


def test_sqlite_chunk_persistence_and_provenance(populated_repo: DocumentRepository):
    doc = populated_repo.list_documents()[0]
    service = ChunkingService(repository=populated_repo, chunk_size=25, chunk_overlap=5)
    service.chunk_document(doc.id)

    chunks = populated_repo.get_chunks_by_document(doc.id)
    assert len(chunks) > 0

    first_chunk = chunks[0]
    provenance = populated_repo.get_chunk(first_chunk.id)
    assert provenance is not None
    assert provenance.id == first_chunk.id
    assert provenance.document_id == doc.id
    assert provenance.filename == doc.filename
    assert provenance.file_type == "pdf"
    assert provenance.page_number == 1
    assert provenance.section_title == "Page 1"
    assert provenance.text == first_chunk.text
    assert provenance.start_char == first_chunk.start_char
    assert provenance.end_char == first_chunk.end_char


def test_foreign_key_cascade_deletion(populated_repo: DocumentRepository):
    doc = populated_repo.list_documents()[0]
    service = ChunkingService(repository=populated_repo)
    service.chunk_document(doc.id)

    assert populated_repo.count_chunks(doc.id) > 0

    # Delete the parent document; foreign key CASCADE must clean up sections AND chunks
    populated_repo.delete_document(doc.id)
    assert populated_repo.count_chunks(doc.id) == 0


def test_normalized_schema_prevents_inconsistent_section_relationship(populated_repo: DocumentRepository):
    """Verify foreign key constraint rejects chunks referencing invalid section_id."""
    invalid_chunk = DocumentChunk(
        id="chunk_invalid_99999",
        document_id="any_doc",
        section_id=999999,  # Does not exist
        chunk_index=0,
        text="Orphan chunk",
        token_count=2,
        start_char=0,
        end_char=12,
    )

    with pytest.raises(sqlite3.IntegrityError):
        with populated_repo._get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO document_chunks (
                        id, section_id, chunk_index, text, token_count, start_char, end_char, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        invalid_chunk.id,
                        invalid_chunk.section_id,
                        invalid_chunk.chunk_index,
                        invalid_chunk.text,
                        invalid_chunk.token_count,
                        invalid_chunk.start_char,
                        invalid_chunk.end_char,
                        invalid_chunk.created_at,
                    ),
                )


def test_section_chunk_uniqueness_constraint(populated_repo: DocumentRepository):
    """Enforce UNIQUE(section_id, chunk_index)."""
    doc = populated_repo.list_documents()[0]
    full_doc = populated_repo.get_document(doc.id)
    sec_id = full_doc.sections[0].id

    chunk1 = DocumentChunk(
        id=generate_chunk_id(sec_id, 0),
        document_id=doc.id,
        section_id=sec_id,
        chunk_index=0,
        text="First",
        token_count=1,
        start_char=0,
        end_char=5,
    )
    chunk_dup = DocumentChunk(
        id=generate_chunk_id(sec_id, 0) + "_alt",
        document_id=doc.id,
        section_id=sec_id,
        chunk_index=0,  # Duplicate section_id + chunk_index
        text="Duplicate index",
        token_count=2,
        start_char=0,
        end_char=15,
    )

    with pytest.raises(sqlite3.IntegrityError):
        populated_repo.save_chunks_for_document(doc.id, [chunk1, chunk_dup])


# ---------------------------------------------------------------------------
# Idempotency, Rebuilding & Batch Processing Tests
# ---------------------------------------------------------------------------


def test_chunking_idempotency_and_rebuild(populated_repo: DocumentRepository):
    doc = populated_repo.list_documents()[0]
    service = ChunkingService(repository=populated_repo, chunk_size=30, chunk_overlap=5)

    # First run
    res1 = service.chunk_document(doc.id)
    assert res1.status == "chunked"
    initial_chunks = populated_repo.count_chunks(doc.id)

    # Second run without rebuild: must skip
    res2 = service.chunk_document(doc.id, rebuild=False)
    assert res2.status == "skipped"
    assert populated_repo.count_chunks(doc.id) == initial_chunks

    # Third run with rebuild and new chunk size
    res3 = service.chunk_document(doc.id, rebuild=True, chunk_size=15, chunk_overlap=2)
    assert res3.status == "rebuilt"
    new_chunks = populated_repo.count_chunks(doc.id)
    # Smaller chunk size should yield more chunks
    assert new_chunks > initial_chunks


def test_chunk_missing_document(populated_repo: DocumentRepository):
    service = ChunkingService(repository=populated_repo)
    res = service.chunk_document("non_existent_doc_id")
    assert res.status == "failed"
    assert "not found" in res.error.lower()


def test_chunk_all_batch_resilience(populated_repo: DocumentRepository):
    # Add a second document to the repo
    doc2 = Document(
        id="doc_second_test",
        filename="second.txt",
        file_type="txt",
        source_path="second.txt",
        content_hash="secondhash123",
        sections=[
            DocumentSection(
                document_id="doc_second_test",
                section_index=0,
                text="Second document text content for batch test.",
            )
        ],
    )
    populated_repo.save_document(doc2)

    service = ChunkingService(repository=populated_repo)
    batch_res = service.chunk_all()

    assert batch_res.total_documents == 2
    assert batch_res.chunked == 2
    assert batch_res.failed == 0
    assert batch_res.total_chunks_created > 0

    summaries = populated_repo.list_chunk_summaries()
    assert len(summaries) == 2
