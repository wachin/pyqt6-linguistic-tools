"""Non-persistent ignored-word state, isolated by locale and scope."""

from __future__ import annotations

from collections.abc import Hashable
from threading import RLock

from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.personal import normalize_personal_word


def _require_identifier(value: Hashable, name: str) -> Hashable:
    if value is None or not isinstance(value, Hashable):
        raise TypeError(f"{name} must be a non-None hashable value")
    return value


class IgnoredWords:
    """Thread-safe, in-memory ignored words for one normalized locale.

    Ignore-once entries use caller-provided document and occurrence identifiers.
    Keeping an occurrence stable across repeated checks prevents a GUI repaint from
    accidentally consuming an ignore-once decision.
    """

    def __init__(self, locale: str, *, case_sensitive: bool = True) -> None:
        if not isinstance(case_sensitive, bool):
            raise TypeError("case_sensitive must be a boolean")
        self.locale = normalize_locale(locale)
        self.case_sensitive = case_sensitive
        self._session: dict[str, str] = {}
        self._documents: dict[Hashable, dict[str, str]] = {}
        self._occurrences: dict[tuple[Hashable, Hashable], tuple[str, str]] = {}
        self._revision = 0
        self._lock = RLock()

    @property
    def revision(self) -> int:
        """Increment whenever ignored state changes."""
        with self._lock:
            return self._revision

    def ignore_once(
        self,
        word: str,
        *,
        document_id: Hashable,
        occurrence_id: Hashable,
    ) -> bool:
        """Ignore one stable occurrence until it or its document is cleared."""
        normalized, word_key = self._normalize(word)
        document = _require_identifier(document_id, "document_id")
        occurrence = _require_identifier(occurrence_id, "occurrence_id")
        location = (document, occurrence)
        with self._lock:
            existing = self._occurrences.get(location)
            if existing is not None and existing[0] == word_key:
                return False
            value = (word_key, normalized)
            self._occurrences[location] = value
            self._revision += 1
            return True

    def ignore_for_document(self, word: str, *, document_id: Hashable) -> bool:
        """Ignore every matching occurrence in one document."""
        normalized, word_key = self._normalize(word)
        document = _require_identifier(document_id, "document_id")
        with self._lock:
            words = self._documents.setdefault(document, {})
            if word_key in words:
                return False
            words[word_key] = normalized
            self._revision += 1
            return True

    def ignore_for_session(self, word: str) -> bool:
        """Ignore every matching occurrence for this locale in the session."""
        normalized, word_key = self._normalize(word)
        with self._lock:
            if word_key in self._session:
                return False
            self._session[word_key] = normalized
            self._revision += 1
            return True

    def is_ignored(
        self,
        word: str,
        *,
        document_id: Hashable | None = None,
        occurrence_id: Hashable | None = None,
    ) -> bool:
        """Return whether session, document, or occurrence state ignores *word*."""
        _, word_key = self._normalize(word)
        if occurrence_id is not None and document_id is None:
            raise ValueError("occurrence_id requires document_id")
        if document_id is not None:
            document_id = _require_identifier(document_id, "document_id")
        if occurrence_id is not None:
            occurrence_id = _require_identifier(occurrence_id, "occurrence_id")
        with self._lock:
            if word_key in self._session:
                return True
            if document_id is None:
                return False
            if word_key in self._documents.get(document_id, {}):
                return True
            if occurrence_id is None:
                return False
            ignored = self._occurrences.get((document_id, occurrence_id))
            return ignored is not None and ignored[0] == word_key

    def session_words(self) -> tuple[str, ...]:
        """Return a deterministic snapshot of session-ignored words."""
        with self._lock:
            return self._sorted(self._session.values())

    def document_words(self, document_id: Hashable) -> tuple[str, ...]:
        """Return a deterministic snapshot for one document."""
        document = _require_identifier(document_id, "document_id")
        with self._lock:
            return self._sorted(self._documents.get(document, {}).values())

    def clear_once(
        self, *, document_id: Hashable, occurrence_id: Hashable
    ) -> bool:
        """Remove one occurrence-scoped decision."""
        document = _require_identifier(document_id, "document_id")
        occurrence = _require_identifier(occurrence_id, "occurrence_id")
        with self._lock:
            if self._occurrences.pop((document, occurrence), None) is None:
                return False
            self._revision += 1
            return True

    def clear_document(self, document_id: Hashable) -> bool:
        """Clear document-wide and occurrence-specific decisions for a document."""
        document = _require_identifier(document_id, "document_id")
        with self._lock:
            changed = self._documents.pop(document, None) is not None
            locations = [
                location for location in self._occurrences if location[0] == document
            ]
            for location in locations:
                del self._occurrences[location]
            changed = changed or bool(locations)
            if changed:
                self._revision += 1
            return changed

    def clear_session(self) -> bool:
        """Clear only locale-wide session decisions."""
        with self._lock:
            if not self._session:
                return False
            self._session.clear()
            self._revision += 1
            return True

    def clear_all(self) -> bool:
        """Clear every ignored-word scope for this locale."""
        with self._lock:
            if not (self._session or self._documents or self._occurrences):
                return False
            self._session.clear()
            self._documents.clear()
            self._occurrences.clear()
            self._revision += 1
            return True

    def _normalize(self, word: str) -> tuple[str, str]:
        normalized = normalize_personal_word(word)
        key = normalized if self.case_sensitive else normalized.casefold()
        return normalized, key

    @staticmethod
    def _sorted(words) -> tuple[str, ...]:
        return tuple(sorted(words, key=lambda word: (word.casefold(), word)))


class IgnoredWordsStore:
    """Own one in-memory ignored-word collection per locale."""

    def __init__(self, *, case_sensitive: bool = True) -> None:
        if not isinstance(case_sensitive, bool):
            raise TypeError("case_sensitive must be a boolean")
        self.case_sensitive = case_sensitive
        self._locales: dict[str, IgnoredWords] = {}
        self._lock = RLock()

    def for_locale(self, locale: str) -> IgnoredWords:
        """Return the stable session collection for *locale*."""
        normalized = normalize_locale(locale)
        with self._lock:
            ignored = self._locales.get(normalized)
            if ignored is None:
                ignored = IgnoredWords(
                    normalized, case_sensitive=self.case_sensitive
                )
                self._locales[normalized] = ignored
            return ignored

    def active_locales(self) -> tuple[str, ...]:
        """Return locales instantiated during this process session."""
        with self._lock:
            return tuple(sorted(self._locales))

    def clear_all(self) -> bool:
        """Clear ignored state for every active locale."""
        with self._lock:
            changed = False
            for ignored in self._locales.values():
                changed = ignored.clear_all() or changed
            return changed


__all__ = ["IgnoredWords", "IgnoredWordsStore"]
