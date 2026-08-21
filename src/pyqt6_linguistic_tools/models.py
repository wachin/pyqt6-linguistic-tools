"""Engine-neutral values returned by linguistic backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from enum import IntEnum
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


class DictionarySourcePriority(IntEnum):
    """Recommended precedence for duplicate dictionary sources."""

    SYSTEM = 100
    MANAGED = 200
    USER = 300


@dataclass(frozen=True, slots=True)
class DictionaryCandidate:
    """Dictionary files offered by one provider for one locale."""

    locale: str
    source: str
    priority: int
    aff_path: Path | None = None
    dic_path: Path | None = None
    thesaurus_dat: Path | None = None
    thesaurus_idx: Path | None = None

    @property
    def has_spelling(self) -> bool:
        return self.aff_path is not None and self.dic_path is not None

    @property
    def has_thesaurus(self) -> bool:
        return self.thesaurus_dat is not None


@dataclass(frozen=True, slots=True)
class DictionaryInfo:
    """Resolved spelling and thesaurus resources for a document locale."""

    locale: str
    display_name: str
    aff_path: Path | None = None
    dic_path: Path | None = None
    thesaurus_dat: Path | None = None
    thesaurus_idx: Path | None = None
    spelling_source: str | None = None
    thesaurus_source: str | None = None
    spelling_locale: str | None = None
    thesaurus_locale: str | None = None

    @property
    def has_spelling(self) -> bool:
        return self.aff_path is not None and self.dic_path is not None

    @property
    def has_thesaurus(self) -> bool:
        return self.thesaurus_dat is not None

    @property
    def uses_language_fallback(self) -> bool:
        return (
            self.spelling_locale not in {None, self.locale}
            or self.thesaurus_locale not in {None, self.locale}
        )


class ValidationStatus(str, Enum):
    """Severity and aggregate outcome of a dictionary validation check."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One machine-readable validation observation."""

    code: str
    status: ValidationStatus
    message: str
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class DictionaryValidationReport:
    """Validation outcome for one spelling or thesaurus component."""

    component: str
    locale: str
    checks: tuple[ValidationCheck, ...]
    encoding: str | None = None
    sampled_entries: tuple[str, ...] = ()

    @property
    def status(self) -> ValidationStatus:
        statuses = {check.status for check in self.checks}
        if ValidationStatus.FAIL in statuses:
            return ValidationStatus.FAIL
        if ValidationStatus.WARNING in statuses:
            return ValidationStatus.WARNING
        return ValidationStatus.PASS

    @property
    def usable(self) -> bool:
        return self.status is not ValidationStatus.FAIL


@dataclass(frozen=True, slots=True)
class DictionaryBundleValidation:
    """Combined reports for every component in an import bundle."""

    reports: tuple[DictionaryValidationReport, ...]

    @property
    def status(self) -> ValidationStatus:
        statuses = {report.status for report in self.reports}
        if not statuses or ValidationStatus.FAIL in statuses:
            return ValidationStatus.FAIL
        if ValidationStatus.WARNING in statuses:
            return ValidationStatus.WARNING
        return ValidationStatus.PASS

    @property
    def usable(self) -> bool:
        return bool(self.reports) and all(report.usable for report in self.reports)


@dataclass(frozen=True, slots=True)
class DictionaryImportResult:
    """Published destination and the validation that authorized it."""

    destination: Path
    validation: DictionaryBundleValidation


@dataclass(frozen=True, slots=True)
class LinguisticCapabilities:
    """Operations currently available to an application for one locale."""

    locale: str
    spell_check: bool
    suggestions: bool
    thesaurus: bool
    personal_dictionary: bool = True
    ignored_words: bool = True
    spelling_source: str | None = None
    thesaurus_source: str | None = None

    @property
    def any_dictionary(self) -> bool:
        return self.spell_check or self.thesaurus


@dataclass(frozen=True, slots=True)
class LinguisticServiceDiagnostic:
    """Recoverable service failure suitable for logs or a host status UI."""

    operation: str
    locale: str
    error_type: str
    message: str
    backend: str | None = None
    path: Path | None = None
    component: str | None = None
    disabled: bool = False
    cause_type: str | None = None
    cause_message: str | None = None


@dataclass(frozen=True, slots=True)
class LinguisticComponentFailure:
    """One isolated spelling or thesaurus component disabled after failure."""

    locale: str
    component: str
    diagnostic: LinguisticServiceDiagnostic
