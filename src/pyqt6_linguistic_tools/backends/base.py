"""Abstract interfaces implemented by every linguistic engine adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pyqt6_linguistic_tools.errors import UnsupportedOperationError
from pyqt6_linguistic_tools.models import BackendMetadata, ThesaurusEntry


class LinguisticBackend(ABC):
    """Lifecycle shared by spelling and thesaurus backends."""

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """Return whether the backend engine can be imported."""

    @property
    @abstractmethod
    def metadata(self) -> BackendMetadata:
        """Return stable backend and active-dictionary metadata."""

    @property
    @abstractmethod
    def loaded(self) -> bool:
        """Return whether the configured dictionary is resident in memory."""

    @abstractmethod
    def load_dictionary(self) -> None:
        """Load the configured dictionary immediately."""

    @abstractmethod
    def unload(self) -> None:
        """Release the loaded engine dictionary."""


class SpellCheckerBackend(LinguisticBackend):
    """Engine-neutral spelling contract."""

    @abstractmethod
    def check_word(self, word: str) -> bool:
        """Return whether *word* is accepted by the active dictionary."""

    @abstractmethod
    def suggest(self, word: str, *, limit: int | None = 8) -> tuple[str, ...]:
        """Return ordered spelling suggestions, optionally bounded by count."""

    def add_word(self, word: str) -> None:
        """Add a word when supported by the concrete backend."""
        raise UnsupportedOperationError(
            "this backend does not support adding words",
            backend=self.metadata.name,
            operation="add_word",
        )

    def remove_word(self, word: str) -> None:
        """Remove a word when supported by the concrete backend."""
        raise UnsupportedOperationError(
            "this backend does not support removing words",
            backend=self.metadata.name,
            operation="remove_word",
        )


class ThesaurusBackend(LinguisticBackend):
    """Engine-neutral thesaurus contract."""

    @abstractmethod
    def lookup(self, word: str) -> ThesaurusEntry | None:
        """Return the structured thesaurus entry for *word*."""

    def synonyms(self, word: str) -> tuple[str, ...]:
        """Return unique synonyms in source order across all meanings."""
        entry = self.lookup(word)
        if entry is None:
            return ()

        seen: set[str] = set()
        result: list[str] = []
        for meaning in entry.meanings:
            # MyThes stores the first related word in the field that PyThes
            # calls ``meaning`` and the remaining words as ``synonyms``.
            for synonym in (meaning.meaning, *meaning.synonyms):
                if synonym not in seen:
                    seen.add(synonym)
                    result.append(synonym)
        return tuple(result)
