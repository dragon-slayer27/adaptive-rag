"""Section-aware, Unicode-safe document chunk splitter."""

from typing import List
from app.chunking.models import DocumentChunk, generate_chunk_id
from app.chunking.tokenizer import BaseTokenizer


class SectionChunker:
    """Splits a DocumentSection's normalized text into ordered, overlapping chunks.

    Guarantees:
    1. section.text[chunk.start_char:chunk.end_char] == chunk.text (exact substring invariant).
    2. chunk.token_count <= chunk_size for every emitted chunk.
    3. Strict forward progress with no infinite loops.
    4. Safe handling of multi-byte Unicode, emojis, math symbols, and CJK text.
    5. Empty or whitespace-only sections return 0 chunks.
    """

    def __init__(
        self,
        tokenizer: BaseTokenizer,
        chunk_size: int = 400,
        chunk_overlap: int = 60,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.tokenizer = tokenizer
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_section(
        self,
        text: str,
        document_id: str,
        section_id: int,
    ) -> List[DocumentChunk]:
        """Split section text into canonical DocumentChunk instances."""
        if not text or not text.strip():
            return []

        total_chars = len(text)
        total_tokens = self.tokenizer.count_tokens(text)

        # If entire section fits within chunk_size, emit a single chunk
        if total_tokens <= self.chunk_size:
            chunk = DocumentChunk(
                id=generate_chunk_id(section_id, 0),
                document_id=document_id,
                section_id=section_id,
                chunk_index=0,
                text=text,
                token_count=total_tokens,
                start_char=0,
                end_char=total_chars,
            )
            assert text[chunk.start_char : chunk.end_char] == chunk.text
            return [chunk]

        chunks: List[DocumentChunk] = []
        chunk_idx = 0
        start_char = 0

        while start_char < total_chars:
            remaining_tokens = self.tokenizer.count_tokens(text[start_char:])
            if remaining_tokens <= self.chunk_size:
                end_char = total_chars
            else:
                # Binary search for the maximum character boundary where tokens <= chunk_size
                low = start_char + 1
                high = total_chars
                best_end = start_char + 1

                while low <= high:
                    mid = (low + high) // 2
                    cand_text = text[start_char:mid]
                    tok_count = self.tokenizer.count_tokens(cand_text)
                    if tok_count <= self.chunk_size:
                        best_end = mid
                        low = mid + 1
                    else:
                        high = mid - 1

                end_char = best_end

                # Optional whitespace snapping if not at document end:
                # Look back up to 20% of the chunk window for a natural whitespace split
                if end_char < total_chars:
                    min_snap = start_char + int((end_char - start_char) * 0.8)
                    last_ws = -1
                    for idx in range(end_char - 1, min_snap, -1):
                        if text[idx] in ("\n", " ", "\t"):
                            last_ws = idx
                            break
                    if last_ws > start_char:
                        end_char = last_ws + 1

            chunk_text = text[start_char:end_char]
            token_count = self.tokenizer.count_tokens(chunk_text)

            # Defensive verification of required invariants
            assert text[start_char:end_char] == chunk_text, "Chunk text must match source slice"
            assert token_count <= self.chunk_size, f"Chunk exceeded size: {token_count} > {self.chunk_size}"

            chunks.append(
                DocumentChunk(
                    id=generate_chunk_id(section_id, chunk_idx),
                    document_id=document_id,
                    section_id=section_id,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    token_count=token_count,
                    start_char=start_char,
                    end_char=end_char,
                )
            )
            chunk_idx += 1

            if end_char >= total_chars:
                break

            # Calculate next_start_char to satisfy requested overlap
            if self.chunk_overlap == 0:
                next_start_char = end_char
            else:
                # Binary search for the start position giving at most chunk_overlap tokens
                low = start_char + 1
                high = end_char - 1
                best_start = end_char - 1

                while low <= high:
                    mid = (low + high) // 2
                    overlap_sub = text[mid:end_char]
                    if self.tokenizer.count_tokens(overlap_sub) <= self.chunk_overlap:
                        best_start = mid
                        high = mid - 1
                    else:
                        low = mid + 1

                next_start_char = best_start

                # Optional forward snap to whitespace
                max_snap = min(end_char - 1, next_start_char + 15)
                for idx in range(next_start_char, max_snap):
                    if text[idx] in ("\n", " ", "\t"):
                        next_start_char = idx + 1
                        break

            # Invariant: strict forward progress
            if next_start_char <= start_char:
                next_start_char = start_char + 1
            if next_start_char >= end_char:
                next_start_char = end_char

            start_char = next_start_char

        return chunks
