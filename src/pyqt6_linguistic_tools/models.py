"""Engine-neutral values returned by linguistic backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Generic, TypeVar


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


class BackendResolutionCode(str, Enum):
    """Machine-readable reason for a backend selection."""

    DEFAULT_SELECTED = "default_selected"
    REQUESTED_SELECTED = "requested_selected"
    REQUESTED_UNKNOWN = "requested_backend_unknown"
    REQUESTED_UNAVAILABLE = "requested_backend_unavailable"
    REQUESTED_INCOMPATIBLE = "requested_backend_incompatible"


@dataclass(frozen=True, slots=True)
class BackendResolutionDiagnostic:
    """Selection details suitable for logs, settings, or diagnostic UIs."""

    code: BackendResolutionCode
    requested_backend: str | None
    selected_backend: str
    locale: str
    fallback_used: bool
    message: str


BackendType = TypeVar("BackendType")


@dataclass(frozen=True, slots=True)
class BackendResolution(Generic[BackendType]):
    """The selected lazy backend and the reason it was selected."""

    backend: BackendType
    diagnostic: BackendResolutionDiagnostic
