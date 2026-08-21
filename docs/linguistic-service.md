# LinguisticService

`LinguisticService` is the widget-independent facade intended for ChordFlow,
ChordPages, and other Python or PyQt6 applications. Host code does not import
Spylls, PyThes, or concrete backend values.

```python
from pyqt6_linguistic_tools import LinguisticService

service = LinguisticService(language="es_EC", namespace="GuitarChordStudio")

service.check_word("computadora")
service.suggestions("computdora")
service.synonyms("rápido")
```

The default registry searches the toolkit's application-managed and manually
imported user locations. Applications may inject a `DictionaryRegistry` with
additional bundled providers. Linux system-dictionary discovery remains a
separate optional provider planned for the final native-backend stage.

## Capabilities and language selection

`set_language()` normalizes identifiers such as `es-ec` to `es_EC` and reports
whether the active language changed. Every lookup also accepts an optional
`locale=` override, allowing background checks for several documents without
temporarily changing the active language.

```python
for locale in service.available_languages():
    capabilities = service.capabilities(locale)
    print(locale, capabilities.spell_check, capabilities.thesaurus)
```

Spelling, suggestions, and thesaurus availability are reported independently.
A spelling-only language remains fully usable when no thesaurus exists, and a
thesaurus-only language can provide synonyms without pretending that spelling
is available. `set_spell_check_enabled()` and `set_thesaurus_enabled()` control
the two features independently.

`dictionary_info()` exposes the engine-neutral selected paths, sources, and
language fallbacks when a diagnostic or settings view needs them.

## Lookup precedence

`check_word()` accepts a word in this order:

```text
Ignored occurrence/document/session
                ↓
Personal dictionary for the locale
                ↓
Selected official spelling backend
```

The context parameters connect the service to `IgnoredWords`:

```python
service.ignore_once(
    "ChordFlow",
    document_id="song-42",
    occurrence_id=(120, 129),
)

service.check_word(
    "ChordFlow",
    document_id="song-42",
    occurrence_id=(120, 129),
)
```

The occurrence range may come directly from `WordToken.span` while the
document revision remains unchanged. Individual occurrence, document, session,
and all-scope clearing methods are also available.

The persistent action used by **Add to dictionary** is separate:

```python
service.add_to_personal_dictionary("requinto")
service.personal_words()
service.remove_from_personal_dictionary("requinto")
```

External personal-dictionary changes made by ChordFlow, ChordPages, or a
backup restore are detected by the existing personal dictionary revision and
file-signature mechanism.

## Lazy engines and bounded backend reuse

The registry is discovered on demand. Resolver selection creates a lazy
backend, but the spelling data is loaded only by the first spelling operation
and the thesaurus data only by the first thesaurus operation. Asking for
spelling never loads PyThes.

Separate bounded LRU caches retain a small number of spelling and thesaurus
backend instances across language changes. `backend_cache_size` controls both
bounds, and `close()` unloads all cached engines. `refresh_dictionaries()`
rediscovers providers and unloads backends pointing to the previous snapshot.

`resolution_diagnostics()` reports default, explicit, and fallback backend
selection. Spelling, suggestion, and thesaurus results use separate bounded
LRU caches with revision-based invalidation; see
[`result-caching.md`](result-caching.md).

## Graceful and strict errors

Desktop applications should not underline every word merely because one
dictionary is absent or malformed. The default `strict=False` behavior is:

- `check_word()` safely accepts a word when no usable official checker exists.
- `suggestions()` and `synonyms()` return empty tuples when unavailable.
- discovery and backend failures produce `LinguisticServiceDiagnostic` values.

```python
def report(diagnostic):
    logger.warning(
        "%s failed for %s: %s",
        diagnostic.operation,
        diagnostic.locale,
        diagnostic.message,
    )

service = LinguisticService(
    "es_EC",
    diagnostic_handler=report,
    diagnostic_limit=100,
)
```

Diagnostics include operation, locale, stable error type, backend, path, and
message. They are bounded and can be inspected or cleared. A failing diagnostic
handler is isolated from the linguistic operation.

Set `strict=True` in tests, command-line tools, or other environments that need
the original structured exception. Invalid API arguments are always raised and
are never mistaken for recoverable engine failures.

Dictionary loading and persistent personal-word writes may perform filesystem
work. Applications should schedule potentially cold operations away from the
Qt GUI thread. The service itself imports no Qt widgets.
