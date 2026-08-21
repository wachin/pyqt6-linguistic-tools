# Architecture overview

This document describes the layered architecture of `pyqt6-linguistic-tools`
and how the modules fit together.

## Layer diagram

```text
Host application (ChordFlow, ChordPages, or another PyQt6 project)
        │
        ├── pyqt6_linguistic_tools.qt  (optional — requires PyQt6)
        │       │
        │       ├── LinguisticTextEditDecorator
        │       ├── SpellCheckHighlighter / LinguisticContextMenu
        │       ├── ThesaurusDialog / DictionaryManagerDialog
        │       └── AsyncSpellCheckController
        │
        └── pyqt6_linguistic_tools  (core — no Qt dependency)
                │
                ├── LinguisticService       (application facade)
                ├── DictionaryRegistry      (discovery + pairing)
                ├── backends                (SpyllsBackend, PyThesBackend)
                ├── personal / ignored      (user word storage)
                ├── tokenizer               (Unicode tokenization)
                └── validation              (dictionary validation)
```

## Core principles

### No PyQt6 in the core

The core package (`pyqt6_linguistic_tools`) must never import PyQt6. All Qt
widgets live in `pyqt6_linguistic_tools.qt` and are loaded lazily through
`__getattr__`. The `[qt]` extra installs PyQt6 for projects that do not
already provide it.

### Portable engines

Spylls and PyThes are the required portable backends for the first release.
They are vendored as submodules under `libs/` and bundled in toolkit
distributions. Native Hunspell and MyThes remain optional post-1.0 work.

### Immutable dictionaries

Official dictionaries are never modified. Personal words live in per-locale
UTF-8 JSON files managed by `PersonalDictionaryStore`. Ignored words live in
memory and are scoped by occurrence, document, or session.

### Component isolation

A spelling or thesaurus failure for one locale never affects other locales or
the other component of the same locale. Failed components are tracked by
`LinguisticComponentFailure` and can be retried.

## Module map

| Module | Responsibility | Docs |
|--------|---------------|------|
| `service.py` | `LinguisticService` — application facade | [`linguistic-service.md`](linguistic-service.md) |
| `registry.py` | `DictionaryRegistry` — discovery and pairing | [`dictionary-registry.md`](dictionary-registry.md) |
| `providers.py` | Dictionary providers (Linux system, managed, user) | [`dictionary-registry.md`](dictionary-registry.md) |
| `backends/` | `SpyllsBackend`, `PyThesBackend` — portable engines | [`backend-api.md`](backend-api.md) |
| `resolver.py` | `SpellBackendResolver`, `ThesaurusBackendResolver` | [`backend-api.md`](backend-api.md) |
| `cache.py` | `BackendCache`, `ResultCache` — LRU caches | [`result-caching.md`](result-caching.md) |
| `personal.py` | `PersonalDictionary`, `PersonalDictionaryStore` | [`personal-dictionary.md`](personal-dictionary.md) |
| `personal_backup.py` | `PersonalDictionaryBackupManager` | [`personal-backups.md`](personal-backups.md) |
| `ignored.py` | `IgnoredWords`, `IgnoredWordsStore` | [`ignored-words.md`](ignored-words.md) |
| `tokenizer.py` | `UnicodeTokenizer` — Unicode/UTF-16 tokenization | [`unicode-tokenizer.md`](unicode-tokenizer.md) |
| `validation.py` | `DictionaryValidator` — Hunspell/MyThes validation | [`dictionary-validation.md`](dictionary-validation.md) |
| `compatibility_report.py` | Dictionary compatibility report | [`testing.md`](testing.md) |
| `locales.py` | Locale normalization and display names | — |
| `errors.py` | Structured error types | [`error-handling.md`](error-handling.md) |
| `catalog.py` | `DictionaryCatalog` — managed download metadata | [`managed-dictionaries.md`](managed-dictionaries.md) |
| `storage.py` | Platform-specific storage paths | — |
| `qt/` | Optional PyQt6 widgets | [`qt-architecture.md`](qt-architecture.md) |

## Data flow

### Spell checking

```text
Application calls service.check_word("hello")
        │
        ├── IgnoredWords?           → accept
        ├── PersonalDictionary?     → accept
        ├── Spell check enabled?    → accept
        ├── Dictionary for locale?  → accept
        ├── Component failed?       → accept
        │
        └── SpellBackendResolver
                │
                └── SpyllsBackend.check_word("hello")
                        │
                        └── Returns True/False
```

### Thesaurus lookup

```text
Application calls service.thesaurus_entry("happy")
        │
        ├── Thesaurus enabled?   → None
        ├── Dictionary for locale? → None
        ├── Component failed?    → None
        │
        └── ThesaurusBackendResolver
                │
                └── PyThesBackend.lookup("happy")
                        │
                        └── Returns ThesaurusEntry | None
```

## Dictionary discovery

```text
DictionaryProvider(s)
        │
        ├── LinuxSystemDictionaryProvider
        │       └── /usr/share/hunspell, /usr/share/mythes, ...
        │
        ├── ManagedDictionaryProvider
        │       └── QStandardPaths::AppLocalDataLocation/{namespace}/dictionaries
        │
        └── UserDictionaryProvider
                └── QStandardPaths::AppLocalDataLocation/{namespace}/user
                        │
                        ▼
                DictionaryRegistry
                        │
                        ├── Pairs .aff/.dic and .dat/.idx by locale
                        ├── Applies source priority (system < managed < user)
                        └── Returns DictionaryInfo for each locale
```

## Installation methods

The toolkit supports three consumption modes:

1. **pip install** in a virtual environment — recommended for development.
2. **Git submodule** — vendored source, as GuitarChordStudio does.
3. **OS package / AppImage** — the packager supplies the import paths.

See [`../README.md`](../README.md) for installation instructions.

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Spylls/PyThes as default engines | Pure Python, no native compilation, portable across all platforms |
| Backend contracts | Applications never import Spylls or PyThes directly |
| Lazy dictionary loading | Dictionaries load on first use, not at service creation |
| Bounded LRU caches | Large dictionaries (e.g. Mongolian, 583K entries) use significant memory |
| Per-locale personal dictionaries | Atomic UTF-8 JSON files, cross-process locking |
| Component isolation | One damaged dictionary never disables the entire service |
| Manual-only CI | Control GitHub Actions minutes, storage, and notifications |