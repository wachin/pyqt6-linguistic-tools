# Result caching and invalidation

`LinguisticService` maintains three independent, bounded least-recently-used
result caches:

```text
(locale, word) -> official spelling result
(locale, word) -> complete spelling suggestion tuple
(locale, word) -> structured thesaurus entry or None
```

The default bound is 2,048 entries in each cache. Applications can use a lower
or higher value according to their document sizes and memory budget:

```python
service = LinguisticService(
    "es_EC",
    result_cache_size=1024,
)
```

Only successful backend calls are cached. A recoverable engine failure retains
the safe `LinguisticService` fallback but does not poison the cache. Missing
thesaurus entries and legitimately empty suggestion tuples are successful
results and are cached distinctly.

Suggestions are requested once from the backend as a complete tuple. Later
calls apply their requested `limit` to that stable cached tuple. This preserves
backend ordering while allowing several menu sizes without repeating an
expensive suggestion search.

## Precedence and correctness

Spelling-result entries represent only the official backend result. They do not
include personal or ignored-word acceptance:

```text
Ignored state (always live)
          ↓
Personal dictionary (revision checked)
          ↓
Cached official spelling result
```

Consequently an ignore-once, document-ignore, or session-ignore decision takes
effect immediately and does not require cache invalidation.

Before using a spelling or suggestion result, the service checks the
`PersonalDictionary.revision` for that locale. A word added, removed, or
restored externally by ChordFlow or ChordPages invalidates that locale's
spelling and suggestion entries. Mutations through the service invalidate them
immediately after durable persistence.

## Dictionary and language invalidation

`DictionaryRegistry.revision` changes when providers are added or removed and
whenever a new discovery snapshot is published. The service compares that
revision after discovery. A changed revision unloads cached backends and clears
all result caches, including changes initiated by an external
`registry.refresh()` call.

`refresh_dictionaries()` performs that process explicitly. A successful active
language change also clears all results as required for future document and UI
state. Files changed outside the toolkit become visible after the registry is
refreshed; the service does not poll arbitrary dictionary files.

`clear_result_caches()` clears all locales or one explicitly supplied locale.
`close()` clears results and unloads the separate backend LRU caches.

## Statistics

`result_cache_stats()` returns immutable `CacheStats` values for spelling,
suggestions, and thesaurus results:

```python
stats = service.result_cache_stats()
print(stats.spelling.hits)
print(stats.suggestions.evictions)
print(stats.thesaurus.size, stats.thesaurus.max_size)
```

Counters include hits, misses, and capacity evictions. Explicit invalidation is
not reported as an eviction. This distinction lets applications and benchmarks
measure whether the chosen bound is effective.

The reusable `ResultCache` class supports cached `None`, deterministic LRU
keys, predicate invalidation, optional statistics reset, and thread-safe access
without importing Qt.
