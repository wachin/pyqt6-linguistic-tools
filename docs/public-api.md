# Public API

This document defines the stable public API surface of `pyqt6-linguistic-tools`.
Applications that import only these names can expect backward compatibility
within the same major version.

## Recommended imports

Most applications need only the service facade and the Qt editor decorator:

```python
from pyqt6_linguistic_tools import LinguisticService
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator

service = LinguisticService(language="en_US")
decorator = LinguisticTextEditDecorator(editor, service)
```

## Core service

`LinguisticService` is the main application-facing facade. It unifies registry
discovery, lazy spelling and thesaurus backends, personal dictionaries,
ignored-word scopes, capability reporting, language switching, and bounded
diagnostics. See [`linguistic-service.md`](linguistic-service.md).

## Qt integration

The `pyqt6_linguistic_tools.qt` package provides optional PyQt6 widgets. Load
them through the lazy `__getattr__` mechanism — they do not require PyQt6 at
import time.

| Name | Source | Description |
|------|--------|-------------|
| `LinguisticTextEditDecorator` | `qt/decorator.py` | Per-editor linguistic state for `QTextEdit`/`QPlainTextEdit` |
| `SpellCheckHighlighter` | `qt/spell_highlighter.py` | Underline misspelled words |
| `LinguisticContextMenu` | `qt/context_menu.py` | Right-click suggestions, add/ignore |
| `ThesaurusDialog` | `qt/thesaurus_dialog.py` | Synonym browser dialog |
| `DictionaryManagerDialog` | `qt/dictionary_manager.py` | Inspect, import, and remove dictionaries |
| `AsyncSpellCheckController` | `qt/async_spellcheck.py` | Background spell checking |
| `QtLanguageSettingsStore` | `qt/language_settings.py` | Persist language per document |
| `QtLinguisticSettings` | `qt/settings.py` | Shared UI defaults |
| `QtIntegrationUnavailableError` | `qt/_compat.py` | Raised when PyQt6 is missing |
| `QtRuntimeInfo` | `qt/_compat.py` | PyQt6 version and runtime info |
| `pyqt6_available` | `qt/_compat.py` | Check whether PyQt6 is installed |
| `require_pyqt6` | `qt/_compat.py` | Guard for Qt-only code paths |
| `default_misspelling_format` | `qt/spell_highlighter.py` | Default QTextCharFormat for errors |
| `preserve_simple_capitalization` | `qt/thesaurus_dialog.py` | Transfer casing during replacement |
| `ContextActionProvider` | `qt/decorator.py` | Callback type for custom menu actions |

## Models

Immutable dataclasses returned by the service. These are safe to inspect,
compare, and construct in tests.

| Name | Description |
|------|-------------|
| `DictionaryInfo` | Resolved spelling and thesaurus paths for a locale |
| `LinguisticCapabilities` | Available operations for one locale |
| `ThesaurusEntry` | A word and its meanings |
| `ThesaurusMeaning` | One meaning and its synonyms |
| `ValidationCheck` | One validation observation |
| `ValidationStatus` | `PASS`, `WARNING`, or `FAIL` |
| `DictionarySourcePriority` | Provider precedence (`SYSTEM`, `MANAGED`, `USER`) |
| `DictionaryValidationReport` | Validation outcome for one component |
| `DictionaryBundleValidation` | Combined reports for a bundle |
| `DictionaryImportResult` | Published destination and validation |
| `LinguisticServiceDiagnostic` | Recoverable failure details |
| `LinguisticComponentFailure` | Disabled component record |
| `BackendResolution` | Selected backend and diagnostic |
| `BackendResolutionCode` | Machine-readable selection reason |
| `BackendResolutionDiagnostic` | Selection details |
| `DictionaryCandidate` | Files offered by one provider |
| `DictionaryMetadata` | Active dictionary metadata |
| `BackendMetadata` | Backend identity and capabilities |
| `BackendCapabilities` | Operations implemented by a backend |
| `ThesaurusEntry` | A word and all its meanings |
| `ThesaurusMeaning` | One meaning and related words |
| `CompatibilityClassification` | `ready`, `limited`, `unsupported` |
| `CompatibilityComponentResult` | Validation result for one component |
| `CompatibilityLocaleResult` | Combined results for one locale |
| `CompatibilityReportMetadata` | Report reproducibility metadata |
| `DictionaryCompatibilityReport` | Complete machine-readable report |

## Errors

All error types are subclasses of `LinguisticError`:

| Error | Raised when |
|-------|-------------|
| `LinguisticError` | Base for all toolkit errors |
| `DictionaryDiscoveryError` | Dictionary discovery fails |
| `DictionaryNotFoundError` | Requested locale not found |
| `DictionaryLoadError` | Dictionary fails to load |
| `DictionaryValidationError` | Validation setup fails |
| `DictionaryImportError` | Import fails |
| `DictionaryCatalogError` | Catalog read fails |
| `PersonalDictionaryError` | Personal dictionary operation fails |
| `PersonalDictionaryBackupError` | Backup or restore fails |
| `BackendResolutionError` | Backend resolution fails |
| `BackendUnavailableError` | Requested backend not available |
| `BackendOperationError` | Backend operation fails |
| `UnsupportedOperationError` | Operation not supported by backend |

## Utilities

| Name | Description |
|------|-------------|
| `DictionaryRegistry` | Discovers and pairs dictionaries by locale |
| `normalize_locale` | Normalize locale strings to `xx_YY` form |
| `locale_display_name` | Human-readable language name |
| `normalize_personal_word` | NFC-normalize a word for storage |
| `normalize_personal_locale` | Normalize locale for personal dictionary storage |
| `logging_diagnostic_handler` | Bridge diagnostics to `logging` |
| `DiagnosticHandler` | Callback type for diagnostics |
| `generate_compatibility_report` | Generate dictionary compatibility report |
| `serialize_report` | Serialize report to deterministic JSON |
| `write_report` | Write report to file |
| `regenerate_thesaurus_index` | Regenerate a MyThes `.idx` from `.dat` |
| `DictionaryValidator` | Validate source dictionary files |
| `load_dictionary_catalog` | Load the managed dictionary catalog |
| `DictionaryCatalog` | Catalog of available managed dictionaries |
| `DictionaryCatalogEntry` | One entry in the catalog |
| `PersonalDictionary` | Per-locale personal word storage |
| `PersonalDictionaryStore` | Manage all personal dictionaries |
| `PersonalDictionaryBackupManager` | Backup and restore personal words |
| `PersonalDictionaryBackupEntry` | One backup entry |
| `PersonalDictionaryBackupPreview` | Backup preview |
| `PersonalDictionaryRestoreEntry` | One restore entry |
| `PersonalDictionaryRestoreResult` | Restore outcome |
| `RestoreMode` | `merge` or `replace` |
| `IgnoredWords` | Ignored-word state for one locale |
| `IgnoredWordsStore` | Manage all ignored-word scopes |
| `DictionaryStoragePaths` | Platform-specific storage paths |
| `application_data_directory` | Application data directory |
| `dictionary_storage_paths` | All storage paths |
| `DictionaryProvider` | Base class for providers |
| `DirectoryDictionaryProvider` | Provider for a directory |
| `LinuxSystemDictionaryProvider` | Discover Linux system dictionaries |
| `ManagedDictionaryProvider` | Application-managed dictionaries |
| `UserDictionaryProvider` | User-imported dictionaries |
| `DEFAULT_LINUX_DICTIONARY_PATHS` | Default system search paths |
| `SpellCheckerBackend` | Abstract spelling backend |
| `ThesaurusBackend` | Abstract thesaurus backend |
| `SpyllsBackend` | Portable Spylls backend |
| `PyThesBackend` | Portable PyThes backend |
| `SpellBackendResolver` | Select and resolve spelling backends |
| `ThesaurusBackendResolver` | Select and resolve thesaurus backends |
| `BackendResolver` | Base resolver class |
| `BackendCache` | LRU cache for backend instances |
| `ResultCache` | LRU result cache |
| `LinguisticResultCacheStats` | Cache statistics |
| `CacheStats` | Generic cache statistics |
| `TokenFilter` | Base class for token filters |
| `UnicodeTokenizer` | Unicode-aware tokenizer |
| `TokenizerConfig` | Tokenizer configuration |
| `WordToken` | One word token |
| `tokenize` | Tokenize a string |
| `BACKUP_FORMAT` | Backup format identifier |
| `BACKUP_VERSION` | Backup version number |
| `__version__` | Package version string |

## Private modules

Modules whose names begin with `_` (e.g. `qt/_compat.py`) are implementation
details. They are not part of the public API and may change without notice.