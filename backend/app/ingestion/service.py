"""Document ingestion service coordinating discovery, parsing, and persistence."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from app.ingestion.models import IngestionItemResult, IngestionResult
from app.ingestion.parsers.base import BaseParser
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.txt_parser import TxtParser
from app.ingestion.storage.repository import DocumentRepository


class DocumentIngestionService:
    """Orchestrates format routing, parsing, normalization, and persistence."""

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        corpus_root: Optional[Path] = None,
    ) -> None:
        self.repository = repository or DocumentRepository()
        self.corpus_root = corpus_root or Path.cwd()

        # Register format parsers
        self.parsers: List[BaseParser] = [
            PdfParser(),
            DocxParser(),
            MarkdownParser(),
            TxtParser(),
        ]
        self._extension_map: Dict[str, BaseParser] = {}
        for parser in self.parsers:
            for ext in parser.supported_extensions:
                self._extension_map[ext.lower()] = parser

    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 content hash of file bytes."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def normalize_relative_path(self, file_path: Path) -> str:
        """Derive a normalized relative path for portable corpus storage."""
        resolved = file_path.resolve()
        try:
            return resolved.relative_to(self.corpus_root.resolve()).as_posix()
        except ValueError:
            try:
                return resolved.relative_to(Path.cwd().resolve()).as_posix()
            except ValueError:
                return file_path.name

    def get_parser(self, file_path: Path) -> Optional[BaseParser]:
        """Look up parser by file extension."""
        return self._extension_map.get(file_path.suffix.lower())

    def ingest_file(self, file_path: Path, on_duplicate: str = "skip") -> IngestionItemResult:
        """Ingest a single file."""
        path_str = str(file_path)

        if not file_path.exists():
            return IngestionItemResult(
                file_path=path_str,
                status="failed",
                error=f"File not found: {file_path}",
            )

        if not file_path.is_file():
            return IngestionItemResult(
                file_path=path_str,
                status="failed",
                error=f"Path is not a regular file: {file_path}",
            )

        parser = self.get_parser(file_path)
        if not parser:
            return IngestionItemResult(
                file_path=path_str,
                status="failed",
                error=f"Unsupported file format: {file_path.suffix}",
            )

        try:
            content_hash = self.compute_hash(file_path)
            rel_path = self.normalize_relative_path(file_path)

            # Check duplicate policy
            existing = self.repository.find_by_content_hash(content_hash)
            if existing:
                if on_duplicate == "skip":
                    return IngestionItemResult(
                        file_path=path_str,
                        status="skipped",
                        document_id=existing.id,
                    )

            # Parse document
            doc = parser.parse(file_path, rel_path, content_hash)

            # Persist to repository
            saved = self.repository.save_document(doc, on_duplicate=on_duplicate)

            status = "replaced" if (existing and on_duplicate == "replace") else "ingested"
            return IngestionItemResult(
                file_path=path_str,
                status=status,
                document_id=doc.id,
            )

        except Exception as exc:
            return IngestionItemResult(
                file_path=path_str,
                status="failed",
                error=str(exc),
            )

    def ingest_directory(
        self, directory_path: Path, on_duplicate: str = "skip", recursive: bool = True
    ) -> IngestionResult:
        """Ingest all supported documents from a directory.

        Fault-tolerant: failures on individual files do not stop the batch.
        """
        result = IngestionResult()

        if not directory_path.exists() or not directory_path.is_dir():
            result.items.append(
                IngestionItemResult(
                    file_path=str(directory_path),
                    status="failed",
                    error=f"Directory does not exist or is not a directory: {directory_path}",
                )
            )
            result.failed = 1
            return result

        pattern = "**/*" if recursive else "*"
        candidates = [
            p for p in sorted(directory_path.glob(pattern))
            if p.is_file() and p.suffix.lower() in self._extension_map
        ]

        result.total_discovered = len(candidates)

        for file_path in candidates:
            item_result = self.ingest_file(file_path, on_duplicate=on_duplicate)
            result.items.append(item_result)

            if item_result.status == "ingested":
                result.ingested += 1
            elif item_result.status == "skipped":
                result.skipped += 1
            elif item_result.status == "replaced":
                result.replaced += 1
            elif item_result.status == "failed":
                result.failed += 1

        return result
