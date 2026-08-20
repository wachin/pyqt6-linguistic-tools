# Personal-dictionary backup and restore

`PersonalDictionaryBackupManager` exports words added by users without copying
or modifying any official Hunspell, LibreOffice, Spylls, or MyThes files. The
same backup is usable on Linux, Windows, and macOS and by both ChordFlow and
ChordPages when they use the same toolkit API.

```python
from pyqt6_linguistic_tools import (
    PersonalDictionaryBackupManager,
    PersonalDictionaryStore,
)

store = PersonalDictionaryStore(namespace="GuitarChordStudio")
backups = PersonalDictionaryBackupManager(store)

# Export every persisted locale.
preview = backups.export("GuitarChordStudio-words.ptlbackup")
print(preview.locales, preview.total_words)

# Export only the active locale, including an empty personal dictionary.
backups.export(
    "Spanish-Ecuador.ptlbackup",
    locales=("es_EC",),
)
```

Export refuses to overwrite an existing destination unless the caller passes
`overwrite=True`. Output uses atomic publication, UTF-8 with literal Unicode,
normalized locale identifiers, NFC-normalized words, and deterministic order.
The suggested `.ptlbackup` suffix distinguishes a backup from an individual
personal-dictionary JSON file.

## Format version 1

The backup is a portable JSON document:

```json
{
  "format": "pyqt6-linguistic-tools.personal-dictionaries",
  "version": 1,
  "dictionaries": [
    {
      "locale": "es_EC",
      "words": ["canción", "niño", "requinto"]
    }
  ]
}
```

It contains no absolute paths, operating-system identifiers, engine settings,
ignored session words, or source dictionary contents.

## Inspect before restoring

`inspect()` validates the complete file without changing local data and returns
a preview with each locale, its words, per-locale counts, and the total count:

```python
preview = backups.inspect("GuitarChordStudio-words.ptlbackup")
for entry in preview.entries:
    print(entry.locale, entry.word_count)
```

The parser accepts a UTF-8 BOM and either Unix or Windows line endings. It
rejects malformed JSON, unknown formats or versions, unsafe locale names,
invalid words, duplicate normalized locales, and excessive file contents
before restoration begins.

## Merge and replace

Merge is the safe default. It preserves existing personal words and adds only
missing backup words:

```python
result = backups.restore("GuitarChordStudio-words.ptlbackup")
```

Replace changes only the selected personal dictionaries. It never deletes
other local locales and never touches official dictionaries:

```python
result = backups.restore(
    "GuitarChordStudio-words.ptlbackup",
    mode="replace",
    locales=("es_EC",),
)
```

A graphical application must show the preview and an explicit warning before
calling replace mode. The core API does not display UI.

`PersonalDictionaryRestoreResult` reports previous, backup, added, and final
word counts for each restored locale.

## Transaction and concurrency behavior

All toolkit personal-dictionary mutations now respect a store-wide cooperative
lock in addition to their per-locale lock. Export therefore observes one
consistent snapshot, and restore cannot interleave with an addition from
ChordFlow or ChordPages.

Restore validates everything first, calculates every final dictionary, stages
all UTF-8 files with `fsync`, and only then publishes them. If publishing any
locale reports a failure, already published locales are rolled back from their
original bytes. Temporary files are removed. Existing malformed personal
dictionaries and symbolic-link targets are not silently replaced.

Applications should perform export and restore outside the Qt GUI thread
because filesystem operations may wait for another process holding the shared
store lock.
