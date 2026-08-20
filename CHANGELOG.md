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
