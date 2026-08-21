# PyQt6 Linguistic Tools

Reusable linguistic infrastructure for Python and PyQt6 applications. The
project will provide a single cross-platform API for spell checking, spelling
suggestions, and synonyms.

Development is currently focused on stabilizing its portable engines:

- [Spylls](https://github.com/zverok/spylls), for Hunspell dictionaries.
- [PyThes](https://github.com/corerd/pythes), for MyThes thesauri.

Native Hunspell and MyThes are outside the scope of this first stage. They may
be added later as optional backends without changing the public API.

## Portable backend API

`SpyllsBackend` and `PyThesBackend` implement stable engine-neutral contracts.
Both load their configured dictionary on first use and can be explicitly
unloaded. `BackendCache` provides an LRU bound for applications that switch
between languages. Engine exceptions and result types never leak through the
public API.

See [`docs/backend-api.md`](docs/backend-api.md) for usage, lifecycle, error,
metadata, and thread-boundary guidance.

`SpellBackendResolver` and `ThesaurusBackendResolver` select Spylls and PyThes
by default on every platform. Optional future engines can register behind the
same contracts. Explicit requests and fallbacks return structured diagnostics
and always preserve the requested document locale.

`DictionaryRegistry` combines prioritized dictionary providers, pairs
Hunspell and MyThes files, supports regional locales, and reports whether a
language has spelling, a thesaurus, or both. See
[`docs/dictionary-registry.md`](docs/dictionary-registry.md).

`ManagedDictionaryProvider` and `UserDictionaryProvider` use shared
cross-platform application-data locations and support safe manual imports.
The validated `dictionaries.json` reader prepares future managed downloads
without performing network access. See
[`docs/managed-dictionaries.md`](docs/managed-dictionaries.md).

`DictionaryValidator` produces structured `PASS`, `WARNING`, and `FAIL`
reports by checking encodings, counts, rules, offsets, representative entries,
and complete Spylls/PyThes loading. Manual imports must pass this validation
before atomic publication. See
[`docs/dictionary-validation.md`](docs/dictionary-validation.md).

`PersonalDictionary` persists NFC-normalized Unicode words in separate UTF-8
files per locale. Atomic replacement and portable per-locale locks allow
ChordFlow and ChordPages to share storage without modifying source
dictionaries. See [`docs/personal-dictionary.md`](docs/personal-dictionary.md).

`IgnoredWords` keeps ignore-once, document-wide, and session-wide spelling
exceptions in memory, separated by locale and entirely independent of the
persistent personal dictionary. See [`docs/ignored-words.md`](docs/ignored-words.md).

`PersonalDictionaryBackupManager` provides validated previews, atomic UTF-8
exports, and transactional merge or replace restoration across locales. Its
portable backups contain only personal words and never alter official source
dictionaries. See [`docs/personal-backups.md`](docs/personal-backups.md).

`UnicodeTokenizer` recognizes words and combining marks across scripts,
preserves linguistic apostrophes and hyphens, excludes configurable technical
regions, and returns exact Python plus Qt-compatible UTF-16 positions. See
[`docs/unicode-tokenizer.md`](docs/unicode-tokenizer.md).

`LinguisticService` unifies registry discovery, lazy spelling and thesaurus
backends, personal dictionaries, ignored-word scopes, capability reporting,
language switching, and bounded diagnostics behind the application-facing API.
See [`docs/linguistic-service.md`](docs/linguistic-service.md).

Bounded LRU caches reuse spelling, suggestion, and thesaurus results while
registry and personal-dictionary revisions provide automatic invalidation.
Cache statistics remain available for tuning without exposing engine objects.
See [`docs/result-caching.md`](docs/result-caching.md).

## Setting up the repository

```bash
git submodule update --init --recursive
python -m pip install -e '.[test]'
python -m pytest
```

The built distribution includes the maintained Spylls and PyThes packages;
applications do not install those engine forks separately.

The fast tests do not require external dictionary downloads. The compatibility
suite uses an explicitly configured LibreOffice dictionary collection:

```bash
LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts \
  python -m pytest -m 'corpus and not full_corpus'
```

The corpus can also be selected with a command-line option:

```bash
python -m pytest -m 'corpus and not full_corpus' \
  --dictionary-corpus=/path/to/dicts
```

The full thesaurus pass is reserved for manual or scheduled execution:

```bash
python -m pytest -m full_corpus --dictionary-corpus=/path/to/dicts
```

The corpus path is never embedded in the package. See
[`docs/engine-baseline.md`](docs/engine-baseline.md) for the verified initial
engine status.

## Performance benchmark

The portable engines include a reproducible, subprocess-isolated benchmark for
load time, lookup and suggestion latency, thesaurus caching, and peak memory:

```bash
python -m pyqt6_linguistic_tools.performance \
  --corpus=/path/to/dicts \
  --output=performance-report.json
```

The default small, medium, and very-large matrix and its initial diagnostic
budgets are documented in
[`docs/performance-budgets.md`](docs/performance-budgets.md). Performance
budgets are review thresholds rather than machine-dependent pytest failures.
