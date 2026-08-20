# Managed and user dictionaries

The toolkit provides cross-platform storage and discovery without requiring
system-wide Hunspell, a DLL, or a native MyThes library. ChordFlow and
ChordPages can share one data root by using the same namespace.

## Data locations

```python
from pyqt6_linguistic_tools import dictionary_storage_paths

paths = dictionary_storage_paths("GuitarChordStudio")
print(paths.managed)
print(paths.user)
```

When PyQt6 is available, the base comes from
`QStandardPaths.GenericDataLocation`. The toolkit does not change the global
`QCoreApplication` organization or application name. Without Qt it uses the
standard platform convention:

- Windows: `%APPDATA%`;
- macOS: `~/Library/Application Support`;
- Linux and other Unix systems: `$XDG_DATA_HOME` or `~/.local/share`.

Constructing a provider never creates a directory. A missing first-run path is
an empty source, not an error. `ensure_directory()` performs creation only
when explicitly requested by the host application.

## Providers

```python
from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)

managed = ManagedDictionaryProvider(namespace="GuitarChordStudio")
user = UserDictionaryProvider(namespace="GuitarChordStudio")
registry = DictionaryRegistry((managed, user))
```

Managed dictionaries use priority 200 and user-imported dictionaries use
priority 300. Therefore a user bundle may override a managed component while
retaining any non-conflicting managed thesaurus or spelling component.

These providers work identically on Linux, Windows, and macOS. They neither
inspect nor modify Linux system dictionary directories; that provider remains
deferred to the final native-system stage.

## Manual import

`UserDictionaryProvider.import_files()` accepts already unpacked files:

```python
destination = user.import_files(
    ["es_EC.aff", "es_EC.dic", "th_es_v2.dat", "th_es_v2.idx"],
    bundle_name="spanish-ecuador",
)
```

The import validates complete Hunspell pairs and MyThes data, rejects unknown
files and duplicate names, stages copies inside the destination filesystem,
loads every staged component through Spylls/PyThes, and publishes the complete
directory with one atomic rename. A failed deep validation removes staging and
attaches its structured report to `DictionaryImportError`. Existing bundles
are never overwritten. Archive extraction and removal require separate,
explicit policies and are not performed by this API. See
[`dictionary-validation.md`](dictionary-validation.md).

## dictionaries.json catalog

The current LibreOffice collection catalog can be inspected safely without
network access:

```python
from pyqt6_linguistic_tools import load_dictionary_catalog

catalog = load_dictionary_catalog("/path/to/dictionaries.json")
spanish = catalog.get("es")
```

The loader validates its schema, safe unique codes, names, HTTPS URLs, sizes,
and optional SHA-256 fields. It treats hyphen and underscore code forms as
equivalent for lookup while preserving the published value.

The current 57-entry catalog does not include SHA-256 hashes, so
`catalog.supports_verified_downloads` is false. For that reason this stage does
not implement automatic downloading or extraction. A future downloader should
require checksums in the release catalog, verify archive size and SHA-256, and
protect extraction against path traversal before publishing into the managed
directory.
