# Personal dictionaries

`PersonalDictionary` stores words added by a user independently of Spylls,
Hunspell, and immutable LibreOffice dictionary files.

```python
from pyqt6_linguistic_tools import PersonalDictionaryStore

store = PersonalDictionaryStore(namespace="GuitarChordStudio")
spanish = store.for_locale("es_EC")

spanish.add_word("ChordFlow")
spanish.add_words(("ChordPages", "canción"))
assert spanish.contains("canción")
print(spanish.words())
```

## Locale and Unicode behavior

Each normalized locale has a separate versioned JSON file, for example
`es_EC.json`. Files are generated as UTF-8 with literal Unicode characters,
not escaped `\uXXXX` sequences. Words are normalized to Unicode NFC before
comparison and persistence, so decomposed and precomposed spellings of
`canción` cannot become duplicate entries.

Words may contain letters from any script, combining marks, apostrophes, and
hyphens. Empty strings, whitespace inside a word, and control characters are
rejected. Exact matching is case-sensitive by default; callers may request
`contains(word, case_sensitive=False)` explicitly.

## Safe persistence

Every mutation follows this sequence:

```text
Acquire per-locale lock
        ↓
Reload latest durable file
        ↓
Apply add/remove/clear
        ↓
Write UTF-8 temporary file + fsync
        ↓
Atomic replace
        ↓
Release lock
```

This prevents partial JSON files and avoids lost sequential updates when
ChordFlow and ChordPages share one storage root. Lock acquisition is portable
and uses exclusive file creation; abandoned locks older than the configured
threshold are recovered. A save failure restores the instance's last durable
snapshot rather than claiming that an unpersisted word exists.

Malformed JSON, unsupported format versions, and locale mismatches raise
`PersonalDictionaryError` and are never silently overwritten. No constructor
or read operation creates a directory or file.

Mutations can wait up to `lock_timeout` when another process owns the locale.
Applications should avoid performing potentially contended persistence on the
Qt GUI thread.

## Application-specific and shared storage

The default location is the `personal` directory returned by
`dictionary_storage_paths(namespace)`. Different namespaces or explicit roots
provide application-specific storage. ChordFlow and ChordPages can explicitly
share words by using the same `GuitarChordStudio` namespace or the same root:

```python
shared = PersonalDictionaryStore(namespace="GuitarChordStudio")
```

`available_locales()` lists persisted locale files. `revision` increments when
an instance observes a new disk snapshot, allowing the future linguistic
service to invalidate its spelling cache after external changes.

Personal dictionaries never open or modify `.aff`, `.dic`, `.dat`, or `.idx`
files. Ignore-once, document-ignore, and session-ignore state remain a separate
non-persistent subsystem.

