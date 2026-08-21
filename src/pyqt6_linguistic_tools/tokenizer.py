"""Unicode-aware word tokenization with exact Python and Qt offsets."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
import re
import unicodedata


TokenFilter = Callable[["WordToken", str], bool]
"""Return ``True`` to retain a token or ``False`` to exclude it."""


_APOSTROPHES = frozenset(("'", "\N{RIGHT SINGLE QUOTATION MARK}"))
_HYPHENS = frozenset(
    (
        "-",
        "\N{HYPHEN}",
        "\N{NON-BREAKING HYPHEN}",
    )
)
_URL_RE = re.compile(
    r"(?i)(?<!\w)(?:https?://|ftp://|www\.)[^\s<>{}\[\]]+"
)
_EMAIL_RE = re.compile(
    r"(?i)(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@(?:[\w-]+\.)+[\w-]{2,}"
)


@dataclass(frozen=True, slots=True)
class WordToken:
    """One source-preserving word and its half-open positional ranges."""

    text: str
    start: int
    end: int
    utf16_start: int
    utf16_end: int

    @property
    def span(self) -> tuple[int, int]:
        """Return the half-open Python string range."""
        return self.start, self.end

    @property
    def utf16_span(self) -> tuple[int, int]:
        """Return the half-open range used by Qt text cursor positions."""
        return self.utf16_start, self.utf16_end

    @property
    def normalized(self) -> str:
        """Return NFC text for dictionary lookup without changing source offsets."""
        return unicodedata.normalize("NFC", self.text)


@dataclass(frozen=True, slots=True)
class TokenizerConfig:
    """Portable lexical and built-in exclusion settings."""

    allow_apostrophes: bool = True
    allow_hyphens: bool = True
    exclude_urls: bool = True
    exclude_emails: bool = True
    include_numbers: bool = False
    include_alphanumeric: bool = False
    excluded_tokens: frozenset[str] = field(default_factory=frozenset)
    excluded_tokens_case_sensitive: bool = True

    def __post_init__(self) -> None:
        boolean_fields = (
            "allow_apostrophes",
            "allow_hyphens",
            "exclude_urls",
            "exclude_emails",
            "include_numbers",
            "include_alphanumeric",
            "excluded_tokens_case_sensitive",
        )
        for name in boolean_fields:
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a boolean")
        if isinstance(self.excluded_tokens, (str, bytes)):
            raise TypeError("excluded_tokens must be an iterable of strings")
        normalized: set[str] = set()
        for token in self.excluded_tokens:
            if not isinstance(token, str):
                raise TypeError("excluded_tokens must contain only strings")
            value = unicodedata.normalize("NFC", token)
            normalized.add(
                value if self.excluded_tokens_case_sensitive else value.casefold()
            )
        object.__setattr__(self, "excluded_tokens", frozenset(normalized))


class UnicodeTokenizer:
    """Extract dictionary words from Unicode text without normalizing the source."""

    def __init__(
        self,
        config: TokenizerConfig | None = None,
        *,
        token_filters: Iterable[TokenFilter] = (),
    ) -> None:
        if config is not None and not isinstance(config, TokenizerConfig):
            raise TypeError("config must be a TokenizerConfig")
        if isinstance(token_filters, (str, bytes)):
            raise TypeError("token_filters must be an iterable of callables")
        filters = tuple(token_filters)
        if any(not callable(token_filter) for token_filter in filters):
            raise TypeError("token_filters must contain only callables")
        self.config = config or TokenizerConfig()
        self.token_filters = filters

    def tokenize(self, text: str) -> tuple[WordToken, ...]:
        """Return an immutable snapshot of all retained word tokens."""
        return tuple(self.iter_tokens(text))

    def iter_tokens(self, text: str) -> Iterator[WordToken]:
        """Yield retained tokens in source order."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        protected = self._protected_spans(text)
        utf16_offsets = self._utf16_offsets(text)
        protected_index = 0
        position = 0

        while position < len(text):
            while (
                protected_index < len(protected)
                and position >= protected[protected_index][1]
            ):
                protected_index += 1
            if (
                protected_index < len(protected)
                and protected[protected_index][0] <= position
                < protected[protected_index][1]
            ):
                position = protected[protected_index][1]
                continue

            category = unicodedata.category(text[position])
            if category[0] not in {"L", "N"}:
                position += 1
                continue

            start = position
            has_letter = category.startswith("L")
            has_number = category.startswith("N")
            position += 1
            while position < len(text):
                category = unicodedata.category(text[position])
                if category[0] in {"L", "M", "N"}:
                    has_letter = has_letter or category.startswith("L")
                    has_number = has_number or category.startswith("N")
                    position += 1
                    continue
                if self._is_internal_connector(text, position):
                    position += 1
                    continue
                break

            token = WordToken(
                text=text[start:position],
                start=start,
                end=position,
                utf16_start=utf16_offsets[start],
                utf16_end=utf16_offsets[position],
            )
            if self._accepts(token, text, has_letter=has_letter, has_number=has_number):
                yield token

    def _is_internal_connector(self, text: str, position: int) -> bool:
        character = text[position]
        allowed = (
            self.config.allow_apostrophes and character in _APOSTROPHES
        ) or (self.config.allow_hyphens and character in _HYPHENS)
        if not allowed or position + 1 >= len(text):
            return False
        previous_category = unicodedata.category(text[position - 1])
        next_category = unicodedata.category(text[position + 1])
        return previous_category[0] in {"L", "M"} and next_category.startswith("L")

    def _accepts(
        self,
        token: WordToken,
        source: str,
        *,
        has_letter: bool,
        has_number: bool,
    ) -> bool:
        if has_number and not has_letter and not self.config.include_numbers:
            return False
        if (
            has_letter
            and has_number
            and not self.config.include_alphanumeric
        ):
            return False
        comparison = token.normalized
        if not self.config.excluded_tokens_case_sensitive:
            comparison = comparison.casefold()
        if comparison in self.config.excluded_tokens:
            return False
        return all(token_filter(token, source) for token_filter in self.token_filters)

    def _protected_spans(self, text: str) -> tuple[tuple[int, int], ...]:
        spans: list[tuple[int, int]] = []
        if self.config.exclude_urls:
            spans.extend(match.span() for match in _URL_RE.finditer(text))
        if self.config.exclude_emails:
            spans.extend(match.span() for match in _EMAIL_RE.finditer(text))
        if not spans:
            return ()
        spans.sort()
        merged: list[tuple[int, int]] = [spans[0]]
        for start, end in spans[1:]:
            previous_start, previous_end = merged[-1]
            if start <= previous_end:
                merged[-1] = previous_start, max(previous_end, end)
            else:
                merged.append((start, end))
        return tuple(merged)

    @staticmethod
    def _utf16_offsets(text: str) -> list[int]:
        offsets = [0]
        position = 0
        for character in text:
            position += 2 if ord(character) > 0xFFFF else 1
            offsets.append(position)
        return offsets


def tokenize(
    text: str,
    config: TokenizerConfig | None = None,
    *,
    token_filters: Iterable[TokenFilter] = (),
) -> tuple[WordToken, ...]:
    """Convenience wrapper for one stateless tokenization operation."""
    return UnicodeTokenizer(config, token_filters=token_filters).tokenize(text)


__all__ = [
    "TokenFilter",
    "TokenizerConfig",
    "UnicodeTokenizer",
    "WordToken",
    "tokenize",
]
