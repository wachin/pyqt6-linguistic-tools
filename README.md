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

On Linux, `LinuxSystemDictionaryProvider` automatically discovers supported
Hunspell and MyThes files installed in the standard `/usr/share` locations.
They remain read-only and are consumed by the portable Spylls/PyThes engines;
loading `libhunspell` or `libmythes` is not required.

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

Malformed or missing resources are isolated by exact locale and component.
Healthy languages remain available, repeated failures are suppressed, and
structured diagnostics can be bridged to Python logging. See
[`docs/error-handling.md`](docs/error-handling.md).

Fast, Qt-offscreen, curated corpus, and full-corpus test workflows are kept
separate and mapped to their contracts in [`docs/testing.md`](docs/testing.md).
Current operating-system smoke tests and their explicit skip rules are
documented in [`docs/platform-testing.md`](docs/platform-testing.md).
The manually dispatched GitHub Actions fast matrix and corpus workflows are
documented in [`docs/continuous-integration.md`](docs/continuous-integration.md).

Bounded LRU caches reuse spelling, suggestion, and thesaurus results while
registry and personal-dictionary revisions provide automatic invalidation.
Cache statistics remain available for tuning without exposing engine objects.
See [`docs/result-caching.md`](docs/result-caching.md).

The optional `pyqt6_linguistic_tools.qt` package establishes a lazy,
one-directional integration boundary without making PyQt6 a core dependency.
Its editor decorators keep independent per-document languages, optionally
persisted through a host-provided `QSettings`, while sharing one linguistic
service. The language menu distinguishes regional variants and reports
spelling and thesaurus availability. Its Dictionary Manager safely inspects,
imports, and removes only application-owned bundles while leaving system
dictionaries immutable. Install the `[qt]` extra for widgets. See
[`docs/qt-architecture.md`](docs/qt-architecture.md).

## Installation, development, and direct source use

`pip` is an installation tool; it is not a runtime requirement. Running an
application with `python -m application_name` does not inherently require
`pip` or a virtual environment. It requires the application package, this
toolkit, and the necessary runtime dependencies to be discoverable on Python's
import path.

There are three supported ways for a project to consume this toolkit:

1. Install it in a project virtual environment. This is the recommended
   development workflow.
2. Vendor it as source, as GuitarChordStudio does with its Git submodule, and
   arrange the source directories on the application's import path.
3. Include or install it through an operating-system package, AppImage, or
   another application packaging system. In this case the packaging system,
   not the end user, supplies the import paths and dependencies.

### Why a virtual environment is recommended

Debian, Ubuntu, and some derived or other Linux distributions mark their system
Python installation as externally managed. Under the PyPA externally managed
environments specification, `pip` should refuse to add, upgrade, or remove
packages in that interpreter's global environment and direct the user to a
virtual environment instead. This protects packages owned by the operating
system.

This restriction is distribution-dependent; it does not mean that `pip` cannot
be used on Linux. Use `pip` inside a virtual environment. Do not use
`sudo pip`, and do not recommend bypassing the protection with
`--break-system-packages` for normal development.

If the standard `venv` module is unavailable on a Debian-family system, install
the operating system package first:

```bash
sudo apt install python3-venv
```

Then create an isolated environment from the repository:

```bash
git submodule update --init --recursive
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,qt,typing]'
python -m pytest
python -m mypy
```

The environment remains active only in the current shell. Leave it with:

```bash
deactivate
```

On Windows, the equivalent setup is:

```powershell
git submodule update --init --recursive
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,qt,typing]"
python -m pytest
python -m mypy
```

The `[test]` extra installs test dependencies, and `[typing]` installs mypy for
contributors. The `[qt]` extra requests `PyQt6>=6.6` for projects that do not
already provide PyQt6. GuitarChordStudio
does not need to install PyQt6 twice when its own development or packaging
environment already supplies it.

### Using the source checkout without pip

Developers may use the toolkit without installing it through `pip`. This
repository uses a `src` layout and vendors Spylls and PyThes in separate
directories, so all three source roots must be discoverable.

For a one-off Unix shell session from the GuitarChordStudio repository root:

```bash
export PYTHONPATH="$PWD/libs/pyqt6-linguistic-tools/src:$PWD/libs/pyqt6-linguistic-tools/libs/spylls:$PWD/libs/pyqt6-linguistic-tools/libs/pythes${PYTHONPATH:+:$PYTHONPATH}"
python -m application_name
```

Replace `application_name` with the actual module used by the host program.
This command is an example of source-path configuration, not an additional
installation method.

A host application may instead configure the same paths in its development
launcher or bootstrap code before importing `pyqt6_linguistic_tools`. That is
often more convenient for a Git-submodule workflow because contributors can
run the program directly without modifying the system Python installation.
Whichever mechanism is used, PyQt6 and any other non-vendored dependencies must
still be available from the interpreter chosen to run the application.

For released `.deb` packages or AppImages, the packager should install or
bundle the toolkit, PyQt6, Spylls, PyThes, and the selected dictionaries in
locations already known to the packaged interpreter. End users should not need
to create a virtual environment or run `pip` merely to launch the packaged
application.

The maintained Spylls and PyThes source packages are included in toolkit
distributions and in this repository. Applications do not install those engine
forks separately.

Official references:

- [Python `venv` documentation](https://docs.python.org/3/library/venv.html)
- [PyPA guide to installing with `pip` and `venv`](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
- [PyPA externally managed environments specification](https://packaging.python.org/en/latest/specifications/externally-managed-environments/)

## Running the test suite

```bash
python -m pytest
```

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

The full thesaurus pass is reserved for explicit manual execution:

```bash
python -m pytest -m full_corpus --dictionary-corpus=/path/to/dicts
```

Linux system-resource smoke tests can be selected independently. They skip
with a visible reason when the required packages or `es_EC` data are absent:

```bash
python -m pytest -m platform
```

The corpus path is never embedded in the package. See
[`docs/engine-baseline.md`](docs/engine-baseline.md) for the verified initial
engine status.

## Compatibility report

The portable engines include a machine-readable dictionary compatibility report
by locale and component:

```bash
python -m pyqt6_linguistic_tools.compatibility_report \
  /path/to/dicts \
  compatibility-report.json
```

The report is versioned UTF-8 JSON with deterministic ordering, containing
per-locale spelling and thesaurus validation results, classifications
(`ready`, `limited`, `unsupported`), source paths relative to the corpus root,
encodings, and reproducibility metadata (toolkit and engine versions,
Python/platform, generation time).

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
