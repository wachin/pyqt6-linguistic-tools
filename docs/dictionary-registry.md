# Dictionary registry

`DictionaryRegistry` is the engine-independent catalog shared by spelling,
thesaurus, configuration, and future Qt integration. Providers locate files;
the registry pairs and prioritizes them; backend resolvers choose an engine.

```text
DictionaryProvider(s)
        ↓ candidates
DictionaryRegistry
        ↓ DictionaryInfo
SpellBackendResolver / ThesaurusBackendResolver
```

## Directory discovery

`DirectoryDictionaryProvider` recursively discovers complete Hunspell
`.aff/.dic` pairs and MyThes `.dat` files with optional `.idx` files:

```python
from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
)

registry = DictionaryRegistry((
    DirectoryDictionaryProvider(
        "/path/to/dictionaries",
        source="managed",
        priority=DictionarySourcePriority.MANAGED,
    ),
))

languages = registry.discover()
ecuador = registry.get("es_EC")
```

Hyphenation files such as `hyph_es.dic` and incomplete Hunspell pairs are not
reported as spelling dictionaries. MyThes versions and known filename flavors
are removed from locale identity, including `th_ca_ES_v3` and
`th_ru_RU_M_aot_and_v2`. Symlink basenames are preserved so Linux locale aliases
remain discoverable.

## Regional fallback

Exact resources always win. If one component is absent for a regional locale,
the registry may use the language-only component. For example, the LibreOffice
corpus resolves:

```text
es_EC.aff + es_EC.dic + th_es_v2.dat + th_es_v2.idx
```

The returned `DictionaryInfo` keeps this visible:

```python
assert ecuador.locale == "es_EC"
assert ecuador.spelling_locale == "es_EC"
assert ecuador.thesaurus_locale == "es"
assert ecuador.uses_language_fallback
```

This does not change the document locale. Pass
`allow_language_fallback=False` to `get()` when exact-only behavior is needed.
Regional data is never applied in the opposite direction to a generic locale.

## Duplicate priority

Spelling and thesaurus components are resolved independently. This permits a
user spelling dictionary to override a managed spelling dictionary while
retaining the managed thesaurus. Larger integer priorities win:

| Recommended source | Priority |
| --- | ---: |
| System | 100 |
| Managed/application | 200 |
| User | 300 |

Equal priorities retain the first registered provider, making the result
deterministic. The selected source is reported separately as
`spelling_source` and `thesaurus_source`.

## Caching and display names

Discovery results are cached. Adding or removing a provider invalidates the
cache, while `refresh()` explicitly scans every provider again. File-system
discovery should run outside the GUI thread when a source may be slow.

`display_name` uses `QLocale` when PyQt6 is present, producing names such as
`Español (Ecuador)`. A code-based readable fallback remains available when the
core package is used without Qt.

## Linux system dictionaries

`LinuxSystemDictionaryProvider` searches the conventional read-only locations:

```text
/usr/share/hunspell
/usr/share/myspell
/usr/share/myspell/dicts
/usr/share/mythes
```

Missing directories are treated as empty sources and are never created. The
provider exposes no import, removal, or directory-creation operations. On
non-Linux platforms its default root list is empty, although explicit roots
may be supplied for portable tests.

The default `LinguisticService` registry orders system, managed, and user
providers at priorities 100, 200, and 300. Consequently Linux applications
use installed files automatically while still allowing an application-managed
or manually imported component to override the corresponding system component.
Discovery does not load a native library: Spylls reads `.aff/.dic` pairs and
PyThes reads `.dat/.idx` data directly.

The first LibreOffice corpus baseline discovers 90 locale entries: 89 offer
spelling, and generic thesauri are explicitly shared with compatible regional
variants. The corpus tests verify all 23 Spanish regional dictionaries.
