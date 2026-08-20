# Portable backend API

The toolkit exposes engine-neutral interfaces for spelling and thesaurus
operations. Applications import only `pyqt6_linguistic_tools`; Spylls and
PyThes remain private implementation details bundled by the toolkit package.

## Lazy loading

Creating a backend records the dictionary paths but does not read the files:

```python
from pyqt6_linguistic_tools import SpyllsBackend

spelling = SpyllsBackend("/usr/share/hunspell/es_EC", locale="es_EC")
assert not spelling.loaded

is_correct = spelling.check_word("Ecuador")  # Loads es_EC on first use.
suggestions = spelling.suggest("Ecuaddor", limit=8)
```

`load_dictionary()` can be called explicitly by a background worker. Calls are
synchronous at the backend boundary: loading and spelling suggestions must not
run on the Qt GUI thread. `unload()` releases the engine dictionary.

The thesaurus follows the same lifecycle:

```python
from pyqt6_linguistic_tools import PyThesBackend

thesaurus = PyThesBackend("/path/to/th_es_v2.dat", locale="es")
entry = thesaurus.lookup("feliz")
synonyms = thesaurus.synonyms("feliz")
```

`lookup()` returns toolkit `ThesaurusEntry` and `ThesaurusMeaning` values, not
PyThes named tuples. `synonyms()` includes the first related word stored in each
MyThes meaning and removes duplicates while preserving source order.

## Bounded backend cache

`BackendCache` is an LRU cache for language-specific backend instances. Its
default maximum is two dictionaries because large Spylls dictionaries can use
substantial memory:

```python
from pyqt6_linguistic_tools import BackendCache, SpyllsBackend

cache = BackendCache[str, SpyllsBackend](max_size=2)
backend = cache.get_or_create(
    "es_EC",
    lambda: SpyllsBackend("/usr/share/hunspell/es_EC", locale="es_EC"),
)
```

Getting or creating a backend remains lazy. When the cache exceeds its bound,
the least recently used backend is removed and `unload()` is called. `remove()`
and `clear()` also unload removed entries. Host applications may choose a
smaller or larger bound based on their memory budget.

## Errors and capabilities

All adapter failures are translated into subclasses of `LinguisticError`.
They contain stable `backend`, `operation`, and optional `path` attributes; the
original engine exception is retained only as `__cause__` for diagnostics.

`backend.metadata` reports:

- backend name and maintained-fork version;
- supported capabilities;
- configured locale and source paths;
- loaded state and source encoding once loaded.

The initial Spylls backend intentionally does not mutate source `.dic` files.
Its `add_word()` and `remove_word()` methods raise `UnsupportedOperationError`.
Persistent personal dictionaries belong to the future toolkit-level
`PersonalDictionary`, independently of the immutable source dictionary.

## Backend selection

Host applications do not need operating-system conditionals. The spelling and
thesaurus resolvers register the portable engines as their defaults on every
platform:

```python
from pyqt6_linguistic_tools import SpellBackendResolver

resolution = SpellBackendResolver().resolve(
    "/usr/share/hunspell/es_EC",
    locale="es_EC",
)
spelling = resolution.backend       # A lazy SpyllsBackend.
diagnostic = resolution.diagnostic  # Why it was selected.
```

An optional backend can be registered without changing the public service or
Qt APIs:

```python
resolver.register(
    "native-hunspell",
    lambda path, locale: NativeHunspellBackend(path, locale=locale),
    available=NativeHunspellBackend.available,
    compatible=NativeHunspellBackend.supports_dictionary,
)
resolution = resolver.resolve(
    dictionary_path,
    locale="es_EC",
    backend="native-hunspell",
)
```

If an explicitly requested backend is unknown, unavailable, or incompatible,
the resolver selects the portable backend and reports one of these stable
codes:

- `requested_backend_unknown`;
- `requested_backend_unavailable`;
- `requested_backend_incompatible`.

The diagnostic retains the requested backend, selected backend, exact locale,
fallback flag, and a human-readable message. The same dictionary path and
locale are passed to the fallback; the resolver never substitutes `es` for
`es_EC` or otherwise changes the document language.

Pass `allow_fallback=False` for conformance tests or strict configuration. A
failure then raises `BackendResolutionError`. Factory and dictionary-loading
errors also remain errors instead of triggering fallback, so corrupt data or a
broken backend cannot be silently hidden by another engine.
