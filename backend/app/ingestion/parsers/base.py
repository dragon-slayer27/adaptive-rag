"""Abstract parser base class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Set
from app.ingestion.models import Document


class BaseParser(ABC):
    """Abstract interface for format-specific document parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> Set[str]:
        """Set of supported lowercase file extensions including the leading dot (e.g. {'.txt'})."""
        pass

    def can_parse(self, file_path: Path) -> bool:
        """Return True if this parser supports the given file extension."""
        return file_path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def parse(self, file_path: Path, relative_source_path: str, content_hash: str) -> Document:
        """Parse raw document into canonical Document representation.

        Args:
            file_path: Absolute or resolved path to local file for reading.
            relative_source_path: Normalized path relative to corpus root for portable persistence.
            content_hash: Precomputed SHA-256 hex digest of file contents.

        Returns:
            Fully populated canonical Document instance with sections and metadata.
        """
        pass
