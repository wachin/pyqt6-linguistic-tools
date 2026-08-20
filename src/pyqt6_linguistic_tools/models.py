"""Engine-neutral values returned by linguistic backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """Operations implemented by a backend."""

    spell_check: bool = False
    suggestions: bool = False
    personal_words: bool = False
    thesaurus: bool = False
    lazy_loading: bool = True


@dataclass(frozen=True, slots=True)
class DictionaryMetadata:
    """Metadata for the dictionary configured on one backend instance."""

    locale: str
    paths: tuple[Path, ...]
    loaded: bool
    encoding: str | None = None


@dataclass(frozen=True, slots=True)
class BackendMetadata:
    """Backend identity, capabilities, and active dictionary state."""

    name: str
    version: str
    capabilities: BackendCapabilities
    dictionary: DictionaryMetadata


@dataclass(frozen=True, slots=True)
class ThesaurusMeaning:
    """One meaning and its related words."""

    part_of_speech: str
    meaning: str
    synonyms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThesaurusEntry:
    """A thesaurus word and all of its distinct meanings."""

    word: str
    meanings: tuple[ThesaurusMeaning, ...]

