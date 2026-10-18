"""Conservative text normalization utilities.

Applies deterministic cleaning to extracted strings while strictly preserving
meaningful document structure, paragraphs, leading indentation, code blocks,
and international Unicode characters.
"""

import re

# Characters to strip: C0 control codes excluding \t (tab, 0x09) and \n (newline, 0x0A)
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
# 3 or more consecutive newlines collapsed to 2 (retains paragraph breaks)
_EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Conservatively normalize raw extracted text.

    Operations:
    1. Standardize line endings to LF (\n).
    2. Strip non-printable control characters while preserving tabs and newlines.
    3. Remove trailing whitespace from individual lines.
    4. Collapse 3+ consecutive newlines to 2 to standardize paragraph spacing.
    5. Strip leading and trailing empty lines from the full text block.

    Preserved:
    - Meaningful Unicode (diacritics, mathematical symbols, punctuation, quotes).
    - Leading whitespace / indentation (lists, code blocks, tables).
    - Paragraph and section separation.
    """
    if not text:
        return ""

    # Standardize CRLF and CR to LF
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove non-printable control characters
    normalized = _CONTROL_CHAR_REGEX.sub("", normalized)

    # Strip trailing whitespace on each line while preserving leading indentation
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # Collapse excessive vertical whitespace to double newline
    normalized = _EXCESSIVE_NEWLINES_REGEX.sub("\n\n", normalized)

    return normalized.strip()
