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

