# Translations

The toolkit ships its own Qt translations for the optional widget layer. Host
applications do not need to extract or translate dependency strings, and they
keep full control of their own translator.

## Bundled files

`src/pyqt6_linguistic_tools/translations/` contains editable `.ts` sources and
compiled `.qm` catalogs for:

| Language | Source | Compiled |
|---|---|---|
| English (source) | `pyqt6_linguistic_tools_en.ts` | `pyqt6_linguistic_tools_en.qm` |
| Spanish | `pyqt6_linguistic_tools_es.ts` | `pyqt6_linguistic_tools_es.qm` |

The English catalog is an identity translation: it keeps the source text and
exists so hosts can install a catalog for the same language code without a
special case. English also remains the fallback when no catalog matches.

## Installing a catalog

```python
from pyqt6_linguistic_tools.qt import install_toolkit_translations

# None or "system" resolves through QLocale.system().
translator = install_toolkit_translations(app, "es")
```

`install_toolkit_translations()` tries the regional code first and then the
base language: `es_EC` loads `es.qm` when no `es_EC.qm` exists. It returns the
installed `QTranslator`, or `None` when no catalog matches, leaving the English
source strings in place. The helper keeps the translator alive and replaces a
previous toolkit translator, so changing language at runtime is safe.

`uninstall_toolkit_translations(app)` removes the toolkit translator without
touching host translators.

## Host applications and overrides

Qt searches installed translators in reverse installation order. Host
applications can therefore choose the precedence:

```python
host_translator = QTranslator(app)
host_translator.load(":/i18n/myapp_es.qm")
app.installTranslator(host_translator)

# Installed later, so toolkit messages win for overlapping contexts.
install_toolkit_translations(app, "es")
```

The toolkit contexts are distinct from host contexts, so coexistence normally
requires no override. A host that already translates a toolkit context can skip
the toolkit helper for that language, or install its own translator after the
toolkit one to override selected messages.

## Extracted contexts

| Context | Owner |
|---|---|
| `DictionaryManagerWidget` | Embeddable dictionary manager |
| `DictionaryManagerDialog` | Dialog wrapper title |
| `PyQt6LinguisticTools.ThesaurusDialog` | Thesaurus dialog |
| `PyQt6LinguisticTools` | Editor context-menu actions |

The manager uses `self.tr()`; the other modules use
`QCoreApplication.translate()` with literal contexts so `pylupdate6` can
extract the strings.

## Updating translations

```bash
cd libs/pyqt6-linguistic-tools

# Extract/update the source catalog. Existing translations are preserved.
pylupdate6 src/pyqt6_linguistic_tools/qt \
  -ts src/pyqt6_linguistic_tools/translations/pyqt6_linguistic_tools_es.ts

# Edit the .ts file, then compile the runtime catalog.
lrelease src/pyqt6_linguistic_tools/translations/pyqt6_linguistic_tools_es.ts \
  -qm src/pyqt6_linguistic_tools/translations/pyqt6_linguistic_tools_es.qm
```

`pyproject.toml` packages both `translations/*.ts` and `translations/*.qm`, so
the editable sources travel with the wheel for downstream translators.

To add a language:

1. Create `pyqt6_linguistic_tools_<lang>.ts` with `pylupdate6`.
2. Translate the messages and compile the `.qm` with `lrelease`.
3. Add a test for one context/source pair in `tests/test_translations.py`.
4. Update the table above.

## Catalog language names

Dictionary names in `dictionaries.json` are data, not UI strings. The manager
shows installed locales through `locale_display_name()` and falls back to the
catalog's English `name` for download rows, so a translated manager still
displays the catalog labels exactly as published.
