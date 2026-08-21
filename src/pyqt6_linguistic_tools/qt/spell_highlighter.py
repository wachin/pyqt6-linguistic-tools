"""Narrow, cache-aware spell highlighting for Qt text documents."""

from __future__ import annotations

import unicodedata

from pyqt6_linguistic_tools.cache import CacheStats, ResultCache
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.tokenizer import UnicodeTokenizer
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6.QtCore import QObject, pyqtSignal  # noqa: E402
from PyQt6.QtGui import (  # noqa: E402
    QColor,
    QSyntaxHighlighter,
    QTextBlock,
    QTextCharFormat,
    QTextDocument,
)


def default_misspelling_format() -> QTextCharFormat:
    """Return a fresh red wave-underline format suitable for misspellings."""
    text_format = QTextCharFormat()
    text_format.setUnderlineColor(QColor("#d02020"))
    text_format.setUnderlineStyle(
        QTextCharFormat.UnderlineStyle.SpellCheckUnderline
    )
    return text_format


class SpellCheckHighlighter(QSyntaxHighlighter):
    """Underline misspellings one block at a time without generating suggestions."""

    enabled_changed = pyqtSignal(bool)
    tokenizer_changed = pyqtSignal()
    misspelling_format_changed = pyqtSignal()

    def __init__(
        self,
        document: QTextDocument,
        service: LinguisticService,
        *,
        tokenizer: UnicodeTokenizer | None = None,
        enabled: bool = True,
        misspelling_format: QTextCharFormat | None = None,
        cache_size: int = 2048,
        parent: QObject | None = None,
    ) -> None:
        if not isinstance(document, QTextDocument):
            raise TypeError("document must be a QTextDocument")
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if tokenizer is not None and not isinstance(tokenizer, UnicodeTokenizer):
            raise TypeError("tokenizer must be a UnicodeTokenizer")
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        if misspelling_format is not None and not isinstance(
            misspelling_format, QTextCharFormat
        ):
            raise TypeError("misspelling_format must be a QTextCharFormat")
        if parent is not None and not isinstance(parent, QObject):
            raise TypeError("parent must be a QObject or None")

        self._service = service
        self._tokenizer = tokenizer or UnicodeTokenizer()
        self._enabled = enabled
        self._misspelling_format = QTextCharFormat(
            misspelling_format or default_misspelling_format()
        )
        self._statuses: ResultCache[tuple[str, str], bool] = ResultCache(cache_size)
        super().__init__(parent if parent is not None else document)
        if parent is not None:
            self.setDocument(document)
            self.rehighlight()

    @property
    def service(self) -> LinguisticService:
        return self._service

    @property
    def tokenizer(self) -> UnicodeTokenizer:
        return self._tokenizer

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def misspelling_format(self) -> QTextCharFormat:
        return QTextCharFormat(self._misspelling_format)

    def cache_stats(self) -> CacheStats:
        return self._statuses.stats()

    def set_enabled(self, enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        if enabled == self._enabled:
            return False
        self._enabled = enabled
        self.rehighlight()
        self.enabled_changed.emit(enabled)
        return True

    def set_tokenizer(self, tokenizer: UnicodeTokenizer) -> bool:
        if not isinstance(tokenizer, UnicodeTokenizer):
            raise TypeError("tokenizer must be a UnicodeTokenizer")
        if tokenizer is self._tokenizer:
            return False
        self._tokenizer = tokenizer
        self.rehighlight()
        self.tokenizer_changed.emit()
        return True

    def set_misspelling_format(self, text_format: QTextCharFormat) -> bool:
        if not isinstance(text_format, QTextCharFormat):
            raise TypeError("text_format must be a QTextCharFormat")
        if text_format == self._misspelling_format:
            return False
        self._misspelling_format = QTextCharFormat(text_format)
        self.rehighlight()
        self.misspelling_format_changed.emit()
        return True

    def invalidate_word(self, word: str, *, rehighlight: bool = True) -> int:
        """Forget one status and rehighlight only blocks containing that word."""
        if not isinstance(word, str):
            raise TypeError("word must be a string")
        if not isinstance(rehighlight, bool):
            raise TypeError("rehighlight must be a boolean")
        normalized = unicodedata.normalize("NFC", word)
        removed = self._statuses.invalidate(lambda key: key[1] == normalized)
        if rehighlight:
            for block in self._blocks_containing(normalized):
                self.rehighlightBlock(block)
        return removed

    def clear_cache(self, *, rehighlight: bool = True) -> int:
        """Forget every local status, optionally rechecking the document."""
        if not isinstance(rehighlight, bool):
            raise TypeError("rehighlight must be a boolean")
        removed = self._statuses.clear()
        if rehighlight:
            self.rehighlight()
        return removed

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        """Tokenize and underline one block; suggestion generation is forbidden."""
        if not self._enabled:
            return
        language = self._service.language
        for token in self._tokenizer.iter_tokens(text):
            key = (language, token.normalized)
            found, accepted = self._statuses.try_get(key)
            if not found:
                accepted = self._service.check_word(
                    token.normalized,
                    locale=language,
                )
                self._statuses.put(key, accepted)
            if not accepted:
                self.setFormat(
                    token.utf16_start,
                    token.utf16_end - token.utf16_start,
                    self._misspelling_format,
                )

    def _blocks_containing(self, normalized_word: str) -> tuple[QTextBlock, ...]:
        document = self.document()
        if document is None:
            return ()
        result: list[QTextBlock] = []
        block = document.firstBlock()
        while block.isValid():
            if any(
                token.normalized == normalized_word
                for token in self._tokenizer.iter_tokens(block.text())
            ):
                result.append(block)
            block = block.next()
        return tuple(result)


__all__ = ["SpellCheckHighlighter", "default_misspelling_format"]
