"""Narrow, cache-aware spell highlighting for Qt text documents."""

from __future__ import annotations

from collections.abc import Mapping
import unicodedata

from pyqt6_linguistic_tools.cache import CacheStats, ResultCache
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.tokenizer import UnicodeTokenizer
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6 import sip  # noqa: E402
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
    unknown_words_found = pyqtSignal(object)

    def __init__(
        self,
        document: QTextDocument,
        service: LinguisticService,
        *,
        tokenizer: UnicodeTokenizer | None = None,
        enabled: bool = True,
        misspelling_format: QTextCharFormat | None = None,
        cache_size: int = 2048,
        check_on_cache_miss: bool = True,
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
        if not isinstance(check_on_cache_miss, bool):
            raise TypeError("check_on_cache_miss must be a boolean")

        self._service = service
        self._document_id: object = id(document)
        self._tokenizer = tokenizer or UnicodeTokenizer()
        self._enabled = enabled
        self._check_on_cache_miss = check_on_cache_miss
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

    @property
    def document_id(self) -> object:
        return self._document_id

    def set_document_id(self, document_id: object) -> None:
        if document_id is None:
            raise TypeError("document_id must not be None")
        self._document_id = document_id

    @property
    def check_on_cache_miss(self) -> bool:
        return self._check_on_cache_miss

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

    def apply_statuses(self, locale: str, statuses: object) -> int:
        """Cache one worker result batch and refresh only matching blocks."""
        if not isinstance(locale, str):
            raise TypeError("locale must be a string")
        if not isinstance(statuses, Mapping):
            raise TypeError("statuses must be a mapping")
        normalized_statuses: dict[str, bool] = {}
        for word, accepted in statuses.items():
            if not isinstance(word, str) or not isinstance(accepted, bool):
                raise TypeError("statuses must map strings to booleans")
            normalized_statuses[unicodedata.normalize("NFC", word)] = accepted
        if locale != self._service.language:
            return 0
        for word, accepted in normalized_statuses.items():
            self._statuses.put((locale, word), accepted)
        try:
            self.rehighlight()
        except RuntimeError:
            return 0
        return len(normalized_statuses)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        """Tokenize and underline one block; suggestion generation is forbidden."""
        if not self._enabled:
            return
        language = self._service.language
        block_position = self.currentBlock().position()
        ignored = self._service.ignored_words(language)
        unknown: list[str] = []
        for token in self._tokenizer.iter_tokens(text):
            if ignored.is_ignored(
                token.normalized,
                document_id=self._document_id,
                occurrence_id=block_position + token.utf16_start,
            ):
                continue
            key = (language, token.normalized)
            found, accepted = self._statuses.try_get(key)
            if not found:
                if self._check_on_cache_miss:
                    accepted = self._service.check_word(
                        token.normalized,
                        locale=language,
                    )
                    self._statuses.put(key, accepted)
                else:
                    unknown.append(token.normalized)
                    continue
            if not accepted:
                self.setFormat(
                    token.utf16_start,
                    token.utf16_end - token.utf16_start,
                    self._misspelling_format,
                )
        if unknown:
            self.unknown_words_found.emit(tuple(dict.fromkeys(unknown)))

    def _blocks_containing(self, normalized_word: str) -> tuple[QTextBlock, ...]:
        return self._blocks_containing_any({normalized_word})

    def _blocks_containing_any(
        self, normalized_words: set[str]
    ) -> tuple[QTextBlock, ...]:
        document = self.document()
        if document is None or sip.isdeleted(document) or not normalized_words:
            return ()
        result: list[QTextBlock] = []
        block = document.firstBlock()
        while block.isValid():
            if any(
                token.normalized in normalized_words
                for token in self._tokenizer.iter_tokens(block.text())
            ):
                result.append(block)
            block = block.next()
        return tuple(result)


__all__ = ["SpellCheckHighlighter", "default_misspelling_format"]
