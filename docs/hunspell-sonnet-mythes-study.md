# Hunspell, MyThes and Sonnet as design references

This document records why three upstream projects were temporarily vendored
under `third-party/` while `pyqt6-linguistic-tools` was being designed, what
each one taught the project, and where those lessons live in the current code
and test suite.

The three sources were **study material only**:

- they were never imported by the package;
- they were never initialized or built by CI;
- they were never part of a wheel or an sdist;
- they are not runtime, build, or test dependencies.

They have been removed from the repository so that a fresh clone does not
download ~22 MB of unrelated C++ source or imply a dependency that the toolkit
does not have. The portable engines remain the maintained
[Spylls](https://github.com/wachin/spylls) and
[PyThes](https://github.com/wachin/pythes) forks under `libs/`.

## Last studied revisions

The revisions below are the ones pinned when the study submodules were removed
(November 2026). They are recorded so the exact sources can be consulted again
without guessing.

| Project | Upstream | Pinned revision | Role |
|---|---|---|---|
| Hunspell | <https://github.com/hunspell/hunspell> | `f143a42a0b95578c39f8657101624ed44dea6514` | Dictionary format and lookup/suggestion behavior |
| MyThes | <https://github.com/hunspell/mythes> | `3d296572882a81f9efd6de8ff0e43dd71296c2ec` | Thesaurus file format and lookup behavior |
| Sonnet | <https://github.com/vnotex/sonnet> | `73202060c41ac5c5e7b2729a3ddff06c20168885` | Qt spell-checking architecture |

## Sonnet: architectural reference

### What Sonnet is

Sonnet is the KDE Frameworks spell-checking library: a mature C++/Qt framework
with backends for Hunspell, HSpell, Voikko and others, plus editor integration
for `QTextEdit`-style widgets. It is LGPL-2.1-or-later (the checkout also
contains LGPL-2.0-or-later and BSD-3-Clause license files for parts of the
tree). It is a reference for **structure**, not code to port.

### Concepts studied

- **Backend/plugin abstraction.** Applications talk to a spell-checking
  interface; concrete engines are selected behind it instead of being called
  directly.
- **Decorating existing widgets.** `Sonnet::SpellCheckDecorator` attaches
  behavior to an existing text widget without requiring the application to
  subclass it or replace it.
- **Dictionary discovery and language selection.** Finding installed
  dictionaries, pairing spelling and thesaurus data, and letting the caller
  choose or override the language.
- **Automatic language detection concepts.** Detection is a separate concern
  from checking, can be disabled, and must not fight the user while typing.
  (The toolkit deliberately deferred automatic detection; see Phase 28 of the
  project roadmap.)
- **Personal dictionaries and ignored words.** User-added words and per-document
  or per-session ignores are kept outside the immutable official dictionary.
- **Suggestion APIs and context-menu integration.** Suggestions are data, and
  the editor integration owns the presentation, replacing the current word and
  adding to the personal dictionary.
- **Configuration separation.** Editor settings, language state and engine
  configuration are distinct from the linguistic service.
- **Error handling.** An unavailable or broken backend should not crash the
  host application or disable unrelated components.
- **Avoiding direct coupling to Hunspell.** Host applications never include or
  link Hunspell headers.

### Python/PyQt6 equivalents

| Sonnet concept | Toolkit implementation |
|---|---|
| Spell-check backend interface | `backends/base.py` → `SpellCheckerBackend`, `ThesaurusBackend` |
| Backend selection | `resolver.py` → `SpellBackendResolver`, `ThesaurusBackendResolver` |
| Dictionary discovery and pairing | `registry.py`, `providers.py` → `DictionaryRegistry`, system/managed/user providers |
| Language model and selection | `locales.py`, `service.py` → normalized locales, `LinguisticService.set_language()` |
| `SpellCheckDecorator` | `qt/decorator.py` → `LinguisticTextEditDecorator` |
| Highlighting | `qt/spell_highlighter.py` → `SpellCheckHighlighter` |
| Context menu | `qt/context_menu.py` → `LinguisticContextMenu` |
| Personal dictionary | `personal.py` → `PersonalDictionary`, `PersonalDictionaryStore` |
| Ignored words | `ignored.py` → `IgnoredWords`, `IgnoredWordsStore` |
| Thesaurus UI | `qt/thesaurus_dialog.py` → `ThesaurusDialog` |
| Dictionary manager UI | `qt/dictionary_manager.py` → `DictionaryManagerDialog` |
| Settings separation | `qt/settings.py`, `qt/language_settings.py` → `QtLinguisticSettings`, `QtLanguageSettingsStore` |
| Synchronous checking | `qt/async_spellcheck.py` → `AsyncSpellCheckController` (a toolkit addition, not a Sonnet port) |

### What was deliberately not taken

- No C++ code, no line-by-line port, no plugin ABI.
- No KDE Frameworks, Qt5/KF5 build system, or Sonnet runtime dependency.
- No requirement to subclass `QTextEdit`/`QPlainTextEdit`; the decorator is
  reversible and preserves the host's existing menus, signals and behavior.
- No automatic language detection in the 1.0 scope; the interface is left as a
  future, independent feature.
- The toolkit's editor integration and service are Python-first and are tested
  without any Sonnet binary.

## Hunspell: behavioral and dictionary-format reference

### Why it matters

Spylls is a Python port of Hunspell's concepts. When the maintained Spylls fork
needed reinforcement, the original C++ source was the authoritative reference
for what a dictionary means and how lookup and suggestions should behave.
Hunspell is distributed under a GPL/LGPL/MPL tri-license; no Hunspell code was
copied into this project.

### Areas studied

- **File format.** `.aff` directives and `.dic` entries, declared encoding
  (`SET`), flag types and aliases (`AF`, `AM`), and codec handling.
- **Affix rules.** `PFX`/`SFX`, cross-product behavior, rule conditions,
  `FULLSTRIP`, and `ONLYINCOMPOUND`.
- **Compounding.** `COMPOUNDRULE`, `CHECKCOMPOUNDPATTERN`, compound flags and
  boundary rejection.
- **Suggestions.** `REP`, `MAP`, `KEY`, `TRY`, ngram scoring, phonetic
  suggestions (`PHONE`), and the `MAXDIFF`/`ONLYMAXDIFF` knobs.
- **Capitalization and special flags.** `KEEPCASE`, `NEEDAFFIX`,
  `FORBIDDENWORD`, `NOSUGGEST` and related casing behavior.
- **Edge cases.** Legacy encodings, malformed declarations, dictionary-specific
  extensions, and entries that are only valid inside compounds.

### Where it landed

- **Spylls fork** (`libs/spylls`): the directive inventory in
  `docs/hunspell-compatibility.md`, `FULLSTRIP` support, and
  `CHECKCOMPOUNDPATTERN` boundary/replacement/zero-pattern handling, each with
  regression tests and an explicit active/pending baseline.
- **Toolkit validation** (`src/pyqt6_linguistic_tools/validation.py`):
  `SET`/codec checks, declared-versus-actual entry counts, full Spylls parsing,
  representative-word checks, and `PASS`/`WARNING`/`FAIL` reports.
- **Corpus tests:** real LibreOffice dictionaries in UTF-8, ISO-8859-1,
  ISO-8859-2, ISO-8859-7, ISO-8859-13 and ISO-8859-15.
- **Architecture decision:** Spylls is the portable spelling backend on every
  platform; native Hunspell is not linked. The legacy ctypes wrapper that
  exists in GuitarChordStudio is outside this toolkit and is not a dependency
  of it.

The C++ source was also a useful *test oracle* while resolving compatibility
defects, but native comparison is not required for the toolkit's test suite and
was never configured in CI.

## MyThes: behavioral and file-format reference

### Why it matters

PyThes is based on MyThes. The original C++ source and its `data_layout.txt`
were the reference for the `.dat`/`.idx` format and for lookup semantics when
the maintained PyThes fork needed reinforcement. MyThes is BSD-style
(three-clause) licensed; no MyThes code was copied into this project.

### Areas studied

- **`.dat` structure.** The encoding declaration, entries, meanings, synonym
  separators, and the rules for assembling a meaning record.
- **`.idx` structure.** Each indexed word and its byte offset into the `.dat`
  file, the declared entry count, ordering, and what a stale or truncated index
  looks like.
- **Encodings.** Declared encodings, UTF-8 BOMs, CRLF versus LF, and mixed or
  malformed lines.
- **Lookup behavior.** How entries and meanings are returned, how duplicates
  are handled, and what a miss should look like.

### Where it landed

- **PyThes fork** (`libs/pythes`): BOM acceptance, malformed-line warnings,
  complete external-index validation, in-memory index reconstruction, explicit
  `.idx` regeneration, NFC key normalization, and structured errors with path,
  line and offset context.
- **Toolkit validation** (`src/pyqt6_linguistic_tools/validation.py`):
  `.dat`/`.idx` existence, declared encoding and strict decoding, index count
  checks, sampled byte-offset targets, complete PyThes loading, and
  representative lookups.
- **Index tooling:** `regenerate_thesaurus_index()` in the toolkit and the
  PyThes regeneration API, always explicit and atomic, never rewriting a source
  dictionary.
- **Corpus tests:** all 26 LibreOffice thesauri, including the known Polish
  stray line and stale offset, and the Russian BOM index.

## Cross-cutting decisions the study produced

- **Engine-neutral contracts.** Applications never import Spylls or PyThes
  directly; they use `SpellCheckerBackend`, `ThesaurusBackend`,
  `SpellBackendResolver` and `LinguisticService`.
- **Portable by default.** Pure-Python engines keep Linux, Windows and macOS
  identical at the public API, with no native compilation.
- **Immutable dictionaries.** Official files are never rewritten; personal
  words and ignored words have their own storage layers.
- **Component isolation.** A broken spelling or thesaurus component for one
  locale is tracked and retryable, and never disables the other component.
- **Providers own platform differences.** Linux system discovery lives in
  `LinuxSystemDictionaryProvider`; editors never branch on the platform.
- **No native/optional surprises.** Sonnet, native Hunspell and native MyThes
  are not required dependencies. Optional native backends remain a post-1.0
  decision behind the same contracts (roadmap Phase 41).

## Licensing notes

| Project | License observed in the checkout | Used how |
|---|---|---|
| Hunspell | GPL-2.0 / LGPL-2.1 / MPL tri-license (`COPYING`, `COPYING.LESSER`, `COPYING.MPL`) | Read for format/behavior reference only |
| MyThes | BSD-style three-clause (`COPYING`), plus WordNet data terms | Read for format/behavior reference only |
| Sonnet | LGPL-2.1-or-later, with LGPL-2.0-or-later and BSD-3-Clause files | Read for architectural patterns only |

No source code from these projects is present in this repository or in the
published package. The maintained Spylls/PyThes forks are separate repositories
with their own licenses and contribution rules.

## Consulting the sources again

The references are no longer submodules. If a future compatibility defect
requires the original source, clone it **outside** this repository, for example:

```bash
mkdir -p ~/src/study
git clone https://github.com/hunspell/hunspell ~/src/study/hunspell
git -C ~/src/study/hunspell checkout f143a42a0b95578c39f8657101624ed44dea6514

git clone https://github.com/hunspell/mythes ~/src/study/mythes
git -C ~/src/study/mythes checkout 3d296572882a81f9efd6de8ff0e43dd71296c2ec

git clone https://github.com/vnotex/sonnet ~/src/study/sonnet
git -C ~/src/study/sonnet checkout 73202060c41ac5c5e7b2729a3ddff06c20168885
```

Do not add them back as submodules. If a new study is genuinely required,
record its purpose, the pinned revision and the lessons in this document, and
keep the sources out of the package and CI.

## Related documents

- [`engine-baseline.md`](engine-baseline.md): the Spylls and PyThes baselines,
  vendored forks and fork policy.
- [`linguistics-architecture.md`](linguistics-architecture.md): layers, module
  map and data flow.
- [`backend-api.md`](backend-api.md): the engine-neutral contracts.
- [`dictionary-validation.md`](dictionary-validation.md): the Hunspell and
  MyThes file checks.
- [`continuous-integration.md`](continuous-integration.md): why CI initializes
  only the portable engine submodules.
