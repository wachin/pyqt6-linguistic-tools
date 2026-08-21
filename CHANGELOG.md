# Changelog

This project follows Semantic Versioning. During `0.x`, incompatible API
changes are recorded here before a release.

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
