"""Cross-platform linguistic services for Python and PyQt6 applications."""

from pyqt6_linguistic_tools.backends import (
    PyThesBackend,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackend,
)
from pyqt6_linguistic_tools.cache import BackendCache
from pyqt6_linguistic_tools.catalog import (
    DictionaryCatalog,
    DictionaryCatalogEntry,
    load_dictionary_catalog,
)
from pyqt6_linguistic_tools.errors import (
    BackendOperationError,
    BackendResolutionError,
    BackendUnavailableError,
    DictionaryDiscoveryError,
    DictionaryCatalogError,
    DictionaryImportError,
    DictionaryValidationError,
    DictionaryLoadError,
    DictionaryNotFoundError,
    LinguisticError,
    PersonalDictionaryError,
    UnsupportedOperationError,
)
from pyqt6_linguistic_tools.models import (
    BackendCapabilities,
    BackendMetadata,
    BackendResolution,
    BackendResolutionCode,
    BackendResolutionDiagnostic,
    DictionaryMetadata,
    DictionaryCandidate,
    DictionaryBundleValidation,
    DictionaryInfo,
    DictionaryImportResult,
    DictionarySourcePriority,
    DictionaryValidationReport,
    ThesaurusEntry,
    ThesaurusMeaning,
    ValidationCheck,
    ValidationStatus,
)
from pyqt6_linguistic_tools.locales import locale_display_name, normalize_locale
from pyqt6_linguistic_tools.providers import (
    DictionaryProvider,
    DirectoryDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.personal import (
    PersonalDictionary,
    PersonalDictionaryStore,
    normalize_personal_word,
)
from pyqt6_linguistic_tools.registry import DictionaryRegistry
from pyqt6_linguistic_tools.resolver import (
    BackendResolver,
    SpellBackendResolver,
    ThesaurusBackendResolver,
)
from pyqt6_linguistic_tools.storage import (
    DictionaryStoragePaths,
    application_data_directory,
    dictionary_storage_paths,
)
from pyqt6_linguistic_tools.validation import (
    DictionaryValidator,
    regenerate_thesaurus_index,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "BackendCache",
    "BackendCapabilities",
    "BackendMetadata",
    "BackendOperationError",
    "BackendResolution",
    "BackendResolutionCode",
    "BackendResolutionDiagnostic",
    "BackendResolutionError",
    "BackendResolver",
    "BackendUnavailableError",
    "DictionaryLoadError",
    "DictionaryCandidate",
    "DictionaryBundleValidation",
    "DictionaryCatalog",
    "DictionaryCatalogEntry",
    "DictionaryCatalogError",
    "DictionaryDiscoveryError",
    "DictionaryInfo",
    "DictionaryImportError",
    "DictionaryImportResult",
    "DictionaryMetadata",
    "DictionaryNotFoundError",
    "DictionaryProvider",
    "DictionaryRegistry",
    "DictionarySourcePriority",
    "DictionaryStoragePaths",
    "DictionaryValidationReport",
    "DictionaryValidator",
    "DictionaryValidationError",
    "DirectoryDictionaryProvider",
    "LinguisticError",
    "ManagedDictionaryProvider",
    "PersonalDictionary",
    "PersonalDictionaryError",
    "PersonalDictionaryStore",
    "PyThesBackend",
    "SpellCheckerBackend",
    "SpellBackendResolver",
    "SpyllsBackend",
    "ThesaurusBackend",
    "ThesaurusBackendResolver",
    "ThesaurusEntry",
    "ThesaurusMeaning",
    "UnsupportedOperationError",
    "UserDictionaryProvider",
    "ValidationCheck",
    "ValidationStatus",
    "application_data_directory",
    "dictionary_storage_paths",
    "load_dictionary_catalog",
    "locale_display_name",
    "normalize_locale",
    "normalize_personal_word",
    "regenerate_thesaurus_index",
    "__version__",
]
