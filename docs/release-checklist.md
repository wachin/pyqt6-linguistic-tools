# Release checklist

This document records the steps required to publish a stable `1.0.0` release
of `pyqt6-linguistic-tools`. Each step must be verified on the target platform
before the release can proceed.

## Pre-release verification (Linux)

Run these commands from the toolkit root (`libs/pyqt6-linguistic-tools`):

```bash
# 1. Fast deterministic suite
QT_QPA_PLATFORM=offscreen python3 -m pytest -c pyproject.toml -q \
  -m 'not corpus and not platform'

# 2. Static type checking
python3 -m mypy

# 3. Standalone examples import correctly
for example in examples/*.py; do
  python3 -c "compile(open('$example').read(), '$example', 'exec')"
done

# 4. Compatibility report CLI
python3 -m pyqt6_linguistic_tools.compatibility_report --help

# 5. Performance benchmark CLI
python3 -m pyqt6_linguistic_tools.performance --help

# 6. Whitespace check
git diff --check
```

## Linux verification

### System dictionaries

Verify that the toolkit discovers and uses system-installed dictionaries:

```bash
# Install test dictionaries (Debian/Ubuntu)
sudo apt install hunspell-es hunspell-en-us mythes-es mythes-en-us

# Verify discovery
python3 -c "
from pyqt6_linguistic_tools import LinguisticService
s = LinguisticService('es_ES')
print('Languages:', len(s.available_languages()))
print('Has spell check:', s.capabilities().spell_check)
print('Has thesaurus:', s.capabilities().thesaurus)
print('Check word:', s.check_word('casa'))
print('Suggestions:', s.suggestions('cassa'))
"
```

### Offscreen Qt tests

```bash
QT_QPA_PLATFORM=offscreen python3 -c "
from PyQt6.QtWidgets import QApplication, QTextEdit
from pyqt6_linguistic_tools import LinguisticService
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator
app = QApplication([])
editor = QTextEdit()
service = LinguisticService('en_US')
decorator = LinguisticTextEditDecorator(editor, service)
print('Decorator attached:', decorator.enabled)
"
```

### Corpus tests (optional, full corpus)

```bash
python3 -m pytest -m corpus \
  --dictionary-corpus=../../third-party/libreoffice-dictionaries-collection/dicts
```

## Platform-specific verification

### Windows

- [ ] Install Python 3.10+ and PyQt6.
- [ ] Clone the repository with `--recurse-submodules`.
- [ ] Run the fast deterministic suite.
- [ ] Verify that the toolkit does not require Hunspell DLLs.
- [ ] Verify that `ManagedDictionaryProvider` and `UserDictionaryProvider`
      use `QStandardPaths` correctly.
- [ ] Verify that the examples display correctly.

### macOS

- [ ] Install Python 3.10+ and PyQt6.
- [ ] Clone the repository with `--recurse-submodules`.
- [ ] Run the fast deterministic suite.
- [ ] Verify that the toolkit does not require native Hunspell/MyThes.
- [ ] Verify that the examples display correctly.

## Cross-platform checklist

- [ ] `SpyllsBackend` is the default spelling engine on all platforms.
- [ ] `PyThesBackend` is the default thesaurus engine on all platforms.
- [ ] No native Hunspell or MyThes libraries are required.
- [ ] `LinguisticService` works without PyQt6 installed.
- [ ] `LinguisticTextEditDecorator` works with PyQt6 on all platforms.
- [ ] Personal dictionaries work on all platforms.
- [ ] Ignore-word support works on all platforms.
- [ ] Unicode handling is correct (NFC normalization, UTF-16 offsets).
- [ ] Legacy dictionary encodings (ISO-8859-*, Windows-1252) are supported.

## Documentation verification

- [ ] `README.md` — installation, usage, example commands.
- [ ] `docs/linguistics-architecture.md` — architecture overview.
- [ ] `docs/public-api.md` — stable API surface.
- [ ] `docs/deprecation-policy.md` — deprecation cycle.
- [ ] `docs/backend-api.md` — Spylls/PyThes lifecycle.
- [ ] `docs/linguistic-service.md` — service facade.
- [ ] `docs/dictionary-registry.md` — discovery and pairing.
- [ ] `docs/dictionary-validation.md` — validation checks.
- [ ] `docs/testing.md` — test strategy.
- [ ] `docs/qt-architecture.md` — Qt integration.
- [ ] `docs/error-handling.md` — error isolation.
- [ ] `docs/personal-dictionary.md` — personal word storage.
- [ ] `docs/ignored-words.md` — ignored-word scopes.
- [ ] `docs/unicode-tokenizer.md` — tokenization.
- [ ] `docs/result-caching.md` — caching strategy.
- [ ] `docs/managed-dictionaries.md` — managed downloads.
- [ ] `docs/personal-backups.md` — backup/restore.
- [ ] `docs/engine-baseline.md` — engine audit.
- [ ] `docs/performance-budgets.md` — performance baselines.
- [ ] `docs/continuous-integration.md` — CI workflow.
- [ ] `docs/platform-testing.md` — platform test strategy.
- [ ] `CHANGELOG.md` — release notes.

## Reuse verification

- [ ] The examples in `examples/` run without GuitarChordStudio.
- [ ] No GuitarChordStudio imports exist in the toolkit.
- [ ] The toolkit works as a Git submodule.
- [ ] Nested Spylls and PyThes submodules initialize with `--recurse-submodules`.
- [ ] The reuse procedure is documented in `docs/reuse.md`.

## Release procedure

1. Update `__version__` in `src/pyqt6_linguistic_tools/__init__.py` to `1.0.0`.
2. Update `CHANGELOG.md` with the release date.
3. Tag the release: `git tag v1.0.0 && git push --tags`.
4. Build the distribution: `python -m build`.
5. Upload to PyPI: `python -m twine upload dist/*`.
6. Create a GitHub release with the changelog entry.