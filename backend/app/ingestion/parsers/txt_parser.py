"""Plain text document parser with explicit encoding validation."""

from pathlib import Path
from typing import Set, Tuple
from app.ingestion.models import Document, DocumentSection, generate_document_id
from app.ingestion.normalizer import normalize_text
from app.ingestion.parsers.base import BaseParser


class TxtParser(BaseParser):
    """Parser for raw text (.txt) documents."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".txt"}

    def _decode_bytes(self, raw_bytes: bytes, file_name: str) -> Tuple[str, str]:
        """Decode raw bytes using explicit, validated encoding fallback.

        Attempts UTF-8 first, then UTF-8-SIG (BOM), then CP1252.
        Does NOT fall back to blind Latin-1, avoiding silent corruption.
        """
        encodings = ["utf-8", "utf-8-sig", "cp1252"]
        for enc in encodings:
            try:
                decoded = raw_bytes.decode(enc)
                return decoded, enc
            except UnicodeDecodeError:
                continue

        raise ValueError(
            f"Failed to decode text file '{file_name}'. Content is not valid UTF-8 or CP1252."
        )

    def parse(self, file_path: Path, relative_source_path: str, content_hash: str) -> Document:
        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            raise ValueError(f"File is empty: {file_path.name}")

        text, encoding = self._decode_bytes(raw_bytes, file_path.name)
        normalized = normalize_text(text)
        if not normalized:
            raise ValueError(f"File contains no non-whitespace text: {file_path.name}")

        doc_id = generate_document_id(content_hash)
        title = file_path.stem.replace("_", " ").replace("-", " ").strip().title()

        section = DocumentSection(
            document_id=doc_id,
            section_index=0,
            page_number=None,
            section_title=None,
            text=normalized,
        )

        return Document(
            id=doc_id,
            filename=file_path.name,
            title=title,
            file_type="txt",
            source_path=relative_source_path,
            content_hash=content_hash,
            metadata={
                "byte_size": len(raw_bytes),
                "char_count": len(normalized),
                "encoding": encoding,
                "section_count": 1,
            },
            sections=[section],
        )
