"""Cross-platform linguistic services for Python and PyQt6 applications.

The stable public API surface is documented in ``docs/public-api.md``.
Modules, classes, and functions not listed there are implementation details
that may change without notice.

Typical usage::

    from pyqt6_linguistic_tools import LinguisticService
    from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator

    service = LinguisticService(language="en_US")
    decorator = LinguisticTextEditDecorator(editor, service)
"""

from pyqt6_linguistic_tools.backends import (
    PyThesBackend,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackend,
)
from pyqt6_linguistic_tools.cache import (
    BackendCache,
    CacheStats,
    LinguisticResultCacheStats,
    ResultCache,
)
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
    PersonalDictionaryBackupError,
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
    LinguisticCapabilities,
    LinguisticComponentFailure,
    LinguisticServiceDiagnostic,
    ThesaurusEntry,
    ThesaurusMeaning,
    ValidationCheck,
    ValidationStatus,
    CompatibilityClassification,
    CompatibilityComponentResult,
    CompatibilityLocaleResult,
    CompatibilityReportMetadata,
    DictionaryCompatibilityReport,
)
from pyqt6_linguistic_tools.locales import locale_display_name, normalize_locale
from pyqt6_linguistic_tools.ignored import IgnoredWords, IgnoredWordsStore
from pyqt6_linguistic_tools.providers import (
    DEFAULT_LINUX_DICTIONARY_PATHS,
    DictionaryProvider,
    DirectoryDictionaryProvider,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)
from pyqt6_linguistic_tools.personal import (
    PersonalDictionary,
    PersonalDictionaryStore,
    normalize_personal_locale,
    normalize_personal_word,
)
from pyqt6_linguistic_tools.personal_backup import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    PersonalDictionaryBackupEntry,
    PersonalDictionaryBackupManager,
    PersonalDictionaryBackupPreview,
    PersonalDictionaryRestoreEntry,
    PersonalDictionaryRestoreResult,
    RestoreMode,
)
from pyqt6_linguistic_tools.registry import DictionaryRegistry
from pyqt6_linguistic_tools.resolver import (
    BackendResolver,
    SpellBackendResolver,
    ThesaurusBackendResolver,
)
from pyqt6_linguistic_tools.service import (
    DiagnosticHandler,
    LinguisticService,
    logging_diagnostic_handler,
)
from pyqt6_linguistic_tools.storage import (
    DictionaryStoragePaths,
    application_data_directory,
    dictionary_storage_paths,
)
from pyqt6_linguistic_tools.tokenizer import (
    TokenFilter,
    TokenizerConfig,
    UnicodeTokenizer,
    WordToken,
    tokenize,
)
from pyqt6_linguistic_tools.compatibility_report import (
    generate_compatibility_report,
    serialize_report,
    write_report,
)
from pyqt6_linguistic_tools.validation import (
    DictionaryValidator,
    regenerate_thesaurus_index,
)

__version__ = "1.0.0"

__all__ = [
    # Core service
    "DiagnosticHandler",
    "LinguisticService",
    "logging_diagnostic_handler",
    # Registry and providers
    "DEFAULT_LINUX_DICTIONARY_PATHS",
    "DictionaryCandidate",
    "DictionaryInfo",
    "DictionaryProvider",
    "DictionaryRegistry",
    "DictionarySourcePriority",
    "DirectoryDictionaryProvider",
    "LinuxSystemDictionaryProvider",
    "ManagedDictionaryProvider",
    "UserDictionaryProvider",
    # Backends
    "BackendCache",
    "BackendCapabilities",
    "BackendMetadata",
    "BackendResolution",
    "BackendResolutionCode",
    "BackendResolutionDiagnostic",
    "BackendResolver",
    "CacheStats",
    "LinguisticResultCacheStats",
    "PyThesBackend",
    "ResultCache",
    "SpellCheckerBackend",
    "SpellBackendResolver",
    "SpyllsBackend",
    "ThesaurusBackend",
    "ThesaurusBackendResolver",
    # Validation
    "DictionaryBundleValidation",
    "DictionaryImportResult",
    "DictionaryValidationReport",
    "DictionaryValidator",
    "regenerate_thesaurus_index",
    "ValidationCheck",
    "ValidationStatus",
    # Compatibility report
    "CompatibilityClassification",
    "CompatibilityComponentResult",
    "CompatibilityLocaleResult",
    "CompatibilityReportMetadata",
    "DictionaryCompatibilityReport",
    "generate_compatibility_report",
    "serialize_report",
    "write_report",
    # Personal dictionary
    "BACKUP_FORMAT",
    "BACKUP_VERSION",
    "PersonalDictionary",
    "PersonalDictionaryBackupEntry",
    "PersonalDictionaryBackupManager",
    "PersonalDictionaryBackupPreview",
    "PersonalDictionaryRestoreEntry",
    "PersonalDictionaryRestoreResult",
    "PersonalDictionaryStore",
    "RestoreMode",
    "normalize_personal_locale",
    "normalize_personal_word",
    # Ignored words
    "IgnoredWords",
    "IgnoredWordsStore",
    # Locales
    "locale_display_name",
    "normalize_locale",
    # Tokenizer
    "TokenFilter",
    "TokenizerConfig",
    "UnicodeTokenizer",
    "WordToken",
    "tokenize",
    # Capabilities
    "LinguisticCapabilities",
    "LinguisticComponentFailure",
    "LinguisticServiceDiagnostic",
    # Models
    "DictionaryMetadata",
    "ThesaurusEntry",
    "ThesaurusMeaning",
    # Errors
    "BackendOperationError",
    "BackendResolutionError",
    "BackendUnavailableError",
    "DictionaryCatalogError",
    "DictionaryDiscoveryError",
    "DictionaryImportError",
    "DictionaryLoadError",
    "DictionaryNotFoundError",
    "DictionaryValidationError",
    "LinguisticError",
    "PersonalDictionaryBackupError",
    "PersonalDictionaryError",
    "UnsupportedOperationError",
    # Catalog
    "DictionaryCatalog",
    "DictionaryCatalogEntry",
    "load_dictionary_catalog",
    # Storage
    "DictionaryStoragePaths",
    "application_data_directory",
    "dictionary_storage_paths",
    # Version
    "__version__",
]
