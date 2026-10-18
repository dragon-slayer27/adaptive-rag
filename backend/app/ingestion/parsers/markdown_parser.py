"""Markdown parser preserving heading hierarchy and section boundaries."""

from pathlib import Path
import re
from typing import List, Optional, Set, Tuple
from app.ingestion.models import Document, DocumentSection, generate_document_id
from app.ingestion.normalizer import normalize_text
from app.ingestion.parsers.base import BaseParser

_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")


class MarkdownParser(BaseParser):
    """Parser for Markdown (.md, .markdown) documents."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".md", ".markdown"}

    def _split_into_sections(self, content: str) -> Tuple[Optional[str], List[Tuple[Optional[str], str]]]:
        """Split markdown content by ATX headings (# to ######).

        Returns:
            Tuple of (inferred_document_title, list of (section_title, section_text)).
        """
        lines = content.split("\n")
        sections: List[Tuple[Optional[str], List[str]]] = []
        current_title: Optional[str] = None
        current_lines: List[str] = []
        top_title: Optional[str] = None

        for line in lines:
            match = _HEADING_REGEX.match(line.strip())
            if match:
                level_str, heading_text = match.groups()
                # Use first level-1 heading as document title if available
                if len(level_str) == 1 and top_title is None:
                    top_title = heading_text.strip()

                # If we have accumulated lines or a previous heading, close section
                if current_lines or current_title is not None:
                    sections.append((current_title, current_lines))

                current_title = heading_text.strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Append final section
        if current_lines or current_title is not None:
            sections.append((current_title, current_lines))

        result: List[Tuple[Optional[str], str]] = []
        for title, raw_lines in sections:
            joined = "\n".join(raw_lines)
            normalized = normalize_text(joined)
            if normalized or title:
                # If section text is empty but title exists, keep title as content
                content_text = normalized if normalized else title
                result.append((title, content_text))

        return top_title, result

    def parse(self, file_path: Path, relative_source_path: str, content_hash: str) -> Document:
        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            raise ValueError(f"File is empty: {file_path.name}")

        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("utf-8-sig")

        top_title, raw_sections = self._split_into_sections(content)
        if not raw_sections:
            raise ValueError(f"Markdown file contains no readable content: {file_path.name}")

        doc_id = generate_document_id(content_hash)
        title = top_title or file_path.stem.replace("_", " ").replace("-", " ").strip().title()

        sections: List[DocumentSection] = []
        for idx, (sec_title, sec_text) in enumerate(raw_sections):
            sections.append(
                DocumentSection(
                    document_id=doc_id,
                    section_index=idx,
                    page_number=None,
                    section_title=sec_title,
                    text=sec_text,
                )
            )

        total_chars = sum(len(s.text) for s in sections)

        return Document(
            id=doc_id,
            filename=file_path.name,
            title=title,
            file_type="md",
            source_path=relative_source_path,
            content_hash=content_hash,
            metadata={
                "byte_size": len(raw_bytes),
                "char_count": total_chars,
                "section_count": len(sections),
                "headings": [s.section_title for s in sections if s.section_title],
            },
            sections=sections,
        )
