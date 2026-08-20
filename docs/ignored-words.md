# Ignored words

`IgnoredWords` manages temporary spell-check exceptions without writing to a
personal, Hunspell, LibreOffice, or managed dictionary. State is held only in
memory and disappears when its owning process ends.

```python
from pyqt6_linguistic_tools import IgnoredWordsStore

ignored_store = IgnoredWordsStore()
ignored = ignored_store.for_locale("es_EC")

ignored.ignore_once(
    "ChordFlow",
    document_id="song-42",
    occurrence_id=(120, 129),
)
ignored.ignore_for_document("requinto", document_id="song-42")
ignored.ignore_for_session("pentatónica")

if ignored.is_ignored(
    "ChordFlow",
    document_id="song-42",
    occurrence_id=(120, 129),
):
    pass  # Do not show a spelling error for this occurrence.
```

## Scope and lifetime

The three scopes are intentionally distinct:

- `ignore_once()` applies to one word occurrence in one document.
- `ignore_for_document()` applies to every matching word in one document.
- `ignore_for_session()` applies to every matching word for one locale in the
  current process session.

The caller owns document and occurrence identifiers. They may be strings,
integers, tuples, or other hashable values. An occurrence identifier must stay
stable while the same token is repeatedly checked, and the editor integration
must clear or replace it when that token changes. Ignore-once state is not
consumed by a lookup because repainting or incremental checking can inspect the
same token many times.

`clear_once()`, `clear_document()`, `clear_session()`, and `clear_all()` remove
the corresponding state. Closing a document should call `clear_document()` so
document identifiers and occurrence positions are released promptly.

## Locale, Unicode, and case behavior

`IgnoredWordsStore` maintains a separate collection for every normalized
locale. Ignoring a word in `es_EC` therefore does not affect `en_US`. Words use
the same validation and Unicode NFC normalization as `PersonalDictionary`.

Matching is case-sensitive by default. Pass `case_sensitive=False` when
creating `IgnoredWords` or `IgnoredWordsStore` if the host application wants an
ignore decision to cover all casing variants.

The classes are thread-safe and expose a `revision` counter for future spelling
cache invalidation. They perform no filesystem operations and do not import
Qt, so the same core API can be used by ChordFlow, ChordPages, and other Python
or PyQt6 applications.

## Separation from Add to dictionary

The user actions have different lifetimes:

```text
Ignore once/document/session -> IgnoredWords -> memory only
Add to dictionary             -> PersonalDictionary -> persistent UTF-8 file
```

Neither action ever modifies official `.aff`, `.dic`, `.dat`, or `.idx` source
files.
