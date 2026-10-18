"""PDF document parser extracting text with page-level structural preservation."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Set
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from app.ingestion.models import Document, DocumentSection, generate_document_id
from app.ingestion.normalizer import normalize_text
from app.ingestion.parsers.base import BaseParser

logging.getLogger("pypdf").setLevel(logging.ERROR)


class PdfParser(BaseParser):
    """Parser for Portable Document Format (.pdf) files using pypdf."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".pdf"}

    def parse(self, file_path: Path, relative_source_path: str, content_hash: str) -> Document:
        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            raise ValueError(f"File is empty: {file_path.name}")

        try:
            reader = PdfReader(str(file_path))
        except (PdfReadError, Exception) as exc:
            raise ValueError(f"Corrupt or unreadable PDF '{file_path.name}': {exc}") from exc

        page_count = len(reader.pages)
        if page_count == 0:
            raise ValueError(f"PDF contains 0 pages: {file_path.name}")

        doc_id = generate_document_id(content_hash)
        sections: List[DocumentSection] = []
        has_any_text = False

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            normalized = normalize_text(page_text)
            if normalized:
                has_any_text = True

            sections.append(
                DocumentSection(
                    document_id=doc_id,
                    section_index=idx,
                    page_number=page_num,
                    section_title=f"Page {page_num}",
                    text=normalized,
                )
            )

        if not has_any_text:
            raise ValueError(f"PDF contains no extractable text: {file_path.name}")

        # Extract PDF metadata if available
        meta: Dict[str, Any] = {
            "byte_size": len(raw_bytes),
            "page_count": page_count,
            "section_count": len(sections),
        }

        extracted_title = None
        if reader.metadata:
            if reader.metadata.title:
                extracted_title = str(reader.metadata.title).strip()
            if reader.metadata.author:
                meta["author"] = str(reader.metadata.author).strip()
            if reader.metadata.creation_date:
                meta["creation_date"] = str(reader.metadata.creation_date)

        title = extracted_title or file_path.stem.replace("_", " ").replace("-", " ").strip().title()

        return Document(
            id=doc_id,
            filename=file_path.name,
            title=title,
            file_type="pdf",
            source_path=relative_source_path,
            content_hash=content_hash,
            metadata=meta,
            sections=sections,
        )
