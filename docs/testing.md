# Testing strategy

The toolkit separates fast deterministic tests from the external LibreOffice
dictionary corpus. This keeps normal development inexpensive while preserving
real Spylls, PyThes, encoding, regional-locale, and file-format validation.

## Fast suite

Run from the `pyqt6-linguistic-tools` repository:

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -c pyproject.toml -q tests
```

The explicit configuration path is useful when this repository is a submodule
of a larger Python project. It guarantees that the toolkit's `src`, Spylls,
and PyThes source paths are active. Qt tests use the offscreen platform and do
not open windows.

Corpus tests call `pytest.skip()` with a concrete setup message when no corpus
path is configured. They never create fake files under an expected external
path or report a resource-dependent assertion as passing.

## LibreOffice corpus suite

Point either the command-line option or environment variable at the collection
`dicts` directory:

```bash
python3 -m pytest -c pyproject.toml -q tests \
  --dictionary-corpus /path/to/libreoffice-dictionaries-collection/dicts
```

```bash
LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts \
  python3 -m pytest -c pyproject.toml -q tests
```

Use `-m corpus` for only resource-dependent tests. Tests marked
`full_corpus` enumerate all matching files and aggregate failures so one run
reports the complete compatibility picture.

## Coverage map

| Contract | Primary tests |
|---|---|
| Registry, priorities, regional fallback | `test_registry.py`, `corpus/test_registry_corpus.py` |
| Directory, managed, and user providers | `test_registry.py`, `test_managed_providers.py` |
| Spylls backend and portable contract | `test_backends.py`, `corpus/test_backend_contracts.py` |
| PyThes backend and portable contract | `test_backends.py`, `corpus/test_backend_contracts.py` |
| Encodings and malformed sources | `test_validation.py`, `corpus/test_spylls_encodings.py`, `corpus/test_pythes_encodings.py` |
| Resolver selection and fallback | `test_resolver.py` |
| Tokenizer and exact Unicode/UTF-16 offsets | `test_tokenizer.py` |
| Service, cache invalidation, isolation | `test_service.py`, `test_result_cache.py` |
| Personal and ignored words, backups | `test_personal_dictionary.py`, `test_ignored_words.py`, `test_personal_backup.py` |
| QTextEdit and QPlainTextEdit | `test_qtextedit_integration.py`, `test_qplaintextedit_integration.py` |
| Highlighting and asynchronous checks | `test_spell_highlighter.py`, `test_async_spellcheck.py` |
| Context menu, thesaurus, languages | `test_context_menu.py`, `test_thesaurus_dialog.py`, `test_language_selection.py` |
| Dictionary Manager | `test_dictionary_manager.py` |
| Pinned multilingual acceptance matrix | `corpus/test_language_matrix.py` |

The tokenizer fixtures explicitly cover `Señor`, `creación`, `Straße`,
`français`, `Москва`, `d’Artagnan`, and `O'Connor`. The PyThes adapter fixture
covers an existing and absent lookup, multiple meanings, and duplicate related
words; the engine-neutral `synonyms()` result preserves first occurrence order.

## Assertions that remain stable across dictionary releases

Small repository fixtures may assert exact deterministic results. Corpus tests
should assert contractual properties and a few documented acceptance words.
They must not assume an entire suggestion order or synonym list when a newer
LibreOffice dictionary may legitimately change it. The service tests verify
that backend suggestions pass through unchanged rather than replacing them
with toolkit-authored guesses.

## Pinned language acceptance matrix

`corpus/test_language_matrix.py` checks the portable Spylls backend against
real English, Ecuadorian Spanish, French, German, Italian, Brazilian and
European Portuguese, Dutch, Polish, Russian, Ukrainian, Greek, and Turkish
dictionaries. Each case contains several recorded valid words and one clearly
invented rejected word. Both Portuguese regional variants are independent
cases.

The matrix is test data, not an application spelling list. Additional
LibreOffice languages are verified through complete registry discovery rather
than duplicated word lists. When the pinned collection changes, acceptance
expectations must be reviewed against that release before updating this
baseline.
