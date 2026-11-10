# Changelog

This project follows Semantic Versioning.

## Unreleased

- Ship the 57-entry `dictionaries.json` catalog as package data and add
  `load_bundled_dictionary_catalog()`. Move the catalog generator to
  `tools/fetch-dict-list.py`; it records the SHA-256 digest that GitHub exposes
  for release assets and accepts `--dicts-dir` to record spelling/thesaurus
  capabilities. Regenerate the bundled catalog with both checksums and flags.
- Add the verified download pipeline: `download_dictionary()` and
  `install_dictionary_archive()` stream over HTTPS, check the catalog size and
  SHA-256, reject unsafe archive paths/links, validate every component, skip
  malformed regional variants, and publish atomically through
  `ManagedDictionaryProvider`.
- Add an embeddable `DictionaryDownloadManagerWidget` and a large 1180×720
  `DictionaryDownloadManagerDialog` wrapper with automatic downloads in a
  worker thread. The base `DictionaryManagerWidget`/`Dialog` keep the
  host-delegated `download_requested` mode. Add search, state/component
  filters, spelling/thesaurus badges, installed/available groups, a details
  panel, and verified install/remove actions. Add the screenshot at
  `images/01-pyqt6-linguistic-tools.png`.
- Wire the download manager into ChordFlow and ChordPages: both open the shared
  dialog, install into the `guitarchordstudio` managed namespace, refresh the
  service, and attach the toolkit decorator to every editor.
- When a MyThes data set provides no grammatical categories (the Spanish
  LibreOffice thesaurus uses `-` for every entry), hide the empty "Part of
  speech" column, keep each meaning as a bold group with its indented synonyms,
  and show a short explanatory note.
- Add a **Copy** action to the thesaurus dialog. It puts HTML and RTF with
  bold meaning groups and synonym bullets on the clipboard for LibreOffice and
  word processors, alongside Markdown with `**bold**` headings and `-` bullets
  for Markdown editors.
- Ship toolkit-owned Spanish and English translations (`.ts` sources and
  compiled `.qm` catalogs) plus `install_toolkit_translations()`,
  `uninstall_toolkit_translations()` and `translation_candidates()`. Convert
  the thesaurus dialog and context menu to extractable literal translation
  contexts. Hosts keep their own translator and can override messages; see
  [`docs/translations.md`](docs/translations.md).
- Add `create_service()` as the reusable service factory for host applications,
  so providers no longer have to be assembled in each program. Add
  `pyqt6_linguistic_tools_bootstrap.py` for applications that vendor the
  toolkit as a `libs/` git submodule without pip.
- Give the thesaurus window a LibreOffice-style layout: editable **Current
  word**, a **Language** selector populated from the installed thesaurus
  dictionaries (native names such as *Español (Ecuador)*), numbered
  **Alternatives**, an editable **Replace with** field, and **Replace**/
  **Cancel** actions. The selector also lists managed thesaurus bundles on
  Windows and macOS.
- Split the thesaurus browser into an embeddable `ThesaurusWidget` and a thin
  `ThesaurusDialog` wrapper. ChordFlow and ChordPages now share both.
- Add a README banner, badges, a Mermaid architecture diagram, a key-module
  overview, and explicit managed-download guidance for developers. The banner
  SVG, its PNG render, and the conversion script live in `docs/assets/`.
- Remove the Hunspell, MyThes and Sonnet study submodules from `third-party/`.
  The toolkit never imported, built or tested them, and CI only initialized the
  Spylls and PyThes engines. The lessons that shaped the architecture and the
  engine forks are preserved in
  [`docs/hunspell-sonnet-mythes-study.md`](docs/hunspell-sonnet-mythes-study.md).

## 1.0.0

- Stable release of the portable linguistic toolkit for PyQt6 applications.
- Spell checking through Spylls, thesaurus through PyThes, no native
  dependencies required.
- Optional Qt integration: `LinguisticTextEditDecorator`, `ThesaurusDialog`,
  `DictionaryManagerDialog`, `SpellCheckHighlighter`, `LinguisticContextMenu`,
  `AsyncSpellCheckController`.
- Personal dictionaries, ignored words, Unicode tokenizer, and result caching.
- Linux system dictionary discovery, cross-platform managed and user providers.
- Dictionary validation, compatibility reports, and performance benchmarks.
- Standalone examples, GuitarChordStudio integration, and documented reuse
  procedure.
- 276 fast tests, mypy-clean, documented public API with deprecation policy.

## 0.1.0.dev0

- Create the standalone Python package and pytest configuration.
- Record the Spylls and PyThes engine baseline.
- Add configurable LibreOffice corpus tests for spelling encodings and
  thesaurus byte offsets.
- Stabilize PyThes for UTF-8 BOMs and recoverable malformed indexes.
- Add a subprocess-isolated Spylls/PyThes benchmark with machine-readable
  reports, real small/medium/very-large corpus cases, and documented diagnostic
  budgets for loading, lookup, suggestions, caching, and peak memory.
- Add stable spelling and thesaurus backend contracts, portable Spylls and
  PyThes adapters, structured toolkit errors, lazy dictionary loading, and an
  unloading bounded LRU backend cache.
- Bundle the maintained engine packages in toolkit distributions so host
  applications never need to import or install the forks separately.
- Add extensible spelling and thesaurus backend resolvers with portable
  cross-platform defaults, explicit selection, compatibility checks, strict
  mode, locale-preserving fallback, and structured selection diagnostics.
- Add a cached `DictionaryRegistry`, a reusable directory provider, stable
  locale parsing and human-readable names, independent spelling/thesaurus
  source priorities, deterministic duplicate handling, and explicit generic
  language fallback for regional variants.
- Add cross-platform managed and user providers, shared `QStandardPaths` data
  roots, atomic non-overwriting manual import, and strict offline validation of
  the 57-entry `dictionaries.json` catalog for future verified downloads.
- Add structured Hunspell/MyThes validation reports, codec and count checks,
  representative lookups, sampled index-offset verification, explicit safe
  index regeneration, and mandatory deep validation before manual publication.
- Add backend-independent personal dictionaries with per-locale UTF-8 JSON,
  NFC normalization, atomic durable writes, cooperative cross-process locks,
  external-change revisions, and explicitly shared or application-specific
  storage.
- Add thread-safe, non-persistent ignored-word state with separate occurrence,
  document, session, and locale scopes, stable occurrence identities, explicit
  clearing, Unicode normalization, and revision tracking.
- Add versioned cross-platform personal-dictionary backups with complete
  validation and previews, selected or all-locale UTF-8 export, merge and
  replace restore modes, store-wide concurrency protection, staged publication,
  and rollback on multi-locale restore failures.
- Reject unsafe personal-dictionary locale basenames before they can form a
  filesystem path.
- Add a dependency-free Unicode tokenizer with exact Python and UTF-16 source
  offsets, multilingual combining-mark support, internal apostrophes and
  hyphens, URL/email and numeric exclusions, configurable technical tokens,
  and host-supplied contextual filters.
- Add the widget-independent `LinguisticService` facade with language and
  capability management, independently enabled spelling and thesaurus paths,
  lazy bounded backend reuse, personal and ignored-word precedence, safe
  fallbacks, strict mode, refresh lifecycle, and bounded structured diagnostics.
- Add bounded LRU spelling, suggestion, and thesaurus result caches with cached
  empty values, statistics, complete-suggestion reuse, registry revisions, and
  automatic invalidation for language, dictionary, and personal-word changes.
- Establish the optional `pyqt6_linguistic_tools.qt` package boundary with lazy
  PyQt6 detection and version checks, validated shared UI defaults, explicit
  component ownership, packaging through the `[qt]` extra, and core-only import
  guarantees.
- Add complete core and Qt mypy coverage under the Python 3.10 contract, with
  a dedicated dependency extra and a failing GitHub Actions typing job.
- Make every GitHub Actions workflow manually dispatched, make corpus artifact
  uploads opt-in, and retain requested reports for only three days.
- Add machine-readable dictionary compatibility report by locale and component
  with versioned UTF-8 JSON, deterministic ordering, reproducibility metadata,
  and independent spelling/thesaurus classifications (`ready`, `limited`,
  `unsupported`). Includes CLI entry point and GitHub Actions artifact upload
  opt-in with 3-day retention.
- Add standalone examples under `examples/` demonstrating QTextEdit,
  QPlainTextEdit, spell checking, thesaurus, dictionary manager, and a
  full-featured demo that integrates all toolkit features.
- Define the stable public API surface in `docs/public-api.md` and a
  deprecation policy in `docs/deprecation-policy.md`. Reorganize `__all__`
  in `__init__.py` by category. Add `py.typed` marker for PEP 561 static
  type checking support.
- Add `docs/linguistics-architecture.md` with complete architecture overview,
  layer diagram, module map, data-flow diagrams, and key design decisions.
- Integrate the toolkit into GuitarChordStudio: create
  `chordflow/linguistic_service.py` factory, use `LinguisticTextEditDecorator`
  and `ThesaurusDialog` in ChordFlow, update `chordpages/spellcheck.py` to
  re-export toolkit classes.
- Add `docs/release-checklist.md` with pre-release verification steps for
  Linux, Windows, macOS, and cross-platform requirements.
- Add `docs/reuse.md` with documented submodule, pip, and OS package
  integration procedures.
