"""Pytest configuration and shared test fixtures."""

from pathlib import Path
import pytest
from app.ingestion.service import DocumentIngestionService
from app.ingestion.storage.repository import DocumentRepository
from tests.generate_fixtures import create_all_fixtures


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    base = Path(__file__).parent
    return create_all_fixtures(base)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_corpus.db"


@pytest.fixture
def repo(temp_db: Path) -> DocumentRepository:
    return DocumentRepository(db_path=str(temp_db))


@pytest.fixture
def service(repo: DocumentRepository, fixtures_dir: Path) -> DocumentIngestionService:
    return DocumentIngestionService(repository=repo, corpus_root=fixtures_dir)
