"""Tokenizer abstraction and implementations for chunking token estimation."""

from abc import ABC, abstractmethod
from typing import List


class BaseTokenizer(ABC):
    """Abstract interface for tokenizers used in chunking."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in the given text."""
        pass

    @abstractmethod
    def encode(self, text: str) -> List[int]:
        """Encode text into a list of token identifiers."""
        pass

    @abstractmethod
    def decode(self, tokens: List[int]) -> str:
        """Decode a list of token identifiers back into text."""
        pass


class TiktokenTokenizer(BaseTokenizer):
    """Production tokenizer using tiktoken (default encoding: cl100k_base)."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        try:
            import tiktoken
        except ImportError as exc:
            raise RuntimeError(
                "tiktoken is required for TiktokenTokenizer. Install it via `pip install tiktoken`."
            ) from exc

        self.encoding_name = encoding_name
        try:
            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            raise ValueError(f"Unknown or invalid tiktoken encoding: '{encoding_name}'") from exc

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text, disallowed_special=()))

    def encode(self, text: str) -> List[int]:
        if not text:
            return []
        return self._encoding.encode(text, disallowed_special=())

    def decode(self, tokens: List[int]) -> str:
        if not tokens:
            return ""
        return self._encoding.decode(tokens)


class CharacterTokenizer(BaseTokenizer):
    """Test-only tokenizer where each character is considered 1 token.

    Note: This is strictly for deterministic unit tests and must not be used
    as a silent production fallback.
    """

    def count_tokens(self, text: str) -> int:
        return len(text)

    def encode(self, text: str) -> List[int]:
        return [ord(c) for c in text]

    def decode(self, tokens: List[int]) -> str:
        return "".join(chr(t) for t in tokens)
