# Dictionary validation

`DictionaryValidator` validates source files through the same portable engines
used by applications. It never rewrites or converts a source dictionary.

```python
from pyqt6_linguistic_tools import DictionaryValidator

validator = DictionaryValidator(sample_size=8)
report = validator.validate_spelling(
    "/path/es_EC.aff",
    "/path/es_EC.dic",
    locale="es_EC",
    representative_words=("Ecuador", "ecuatoriano", "canción", "niño"),
)
```

Reports contain stable checks with one of three statuses:

- `PASS`: the check completed successfully;
- `WARNING`: the engine can use the dictionary, but recovery or review is
  advisable;
- `FAIL`: the dictionary component is not safe to publish or use.

`report.status` is the highest severity and `report.usable` is false whenever
any check failed. Checks include machine-readable codes, messages, and the
related path, making them suitable for logs and a future Dictionary Manager.

## Hunspell validation

Spelling validation checks:

- `.aff` and `.dic` existence;
- the `SET` declaration and Python codec availability;
- strict decoding, with a warning for preserved legacy flag bytes;
- declared versus actual dictionary entry count;
- complete Spylls parsing of entries and affix rules;
- caller-provided correct words or automatically selected standalone entries.

Explicit representative words are contractual: rejecting one produces
`FAIL`. Automatic sampling reports `WARNING` rather than failure when a
specialized dictionary contains no standalone roots, such as dictionaries
whose entries are only valid inside compounds.

## MyThes validation

Thesaurus validation checks:

- `.dat` existence and optional `.idx` existence;
- declared encoding and strict data decoding;
- index declaration and actual line count;
- evenly distributed sampled byte offsets and their target words;
- complete PyThes loading, including its full external-index validation;
- representative entry lookup and preservation as Python Unicode strings.

A missing index is a usable warning because PyThes can construct one in
memory. A malformed or stale external index is also reported as a warning when
PyThes safely recovers from the original `.dat`; the source remains unchanged.
Malformed data or a failed engine load is a failure.

Index generation is always explicit:

```python
from pyqt6_linguistic_tools import regenerate_thesaurus_index

generated = regenerate_thesaurus_index("/path/th_es_v2.dat")
```

Existing destinations are protected unless `overwrite=True` is supplied. The
generated index is validated before publication by the maintained PyThes fork,
and engine-specific exceptions are translated into toolkit errors.

## Import boundary

`UserDictionaryProvider.import_files()` now performs deep validation inside
its temporary staging directory before the atomic rename. A `FAIL` raises
`DictionaryImportError`, attaches the complete report as `error.validation`,
removes staging, and publishes nothing. Recoverable warnings remain available
and do not cause source modification. Applications that need the successful
report can call `import_validated_files()`; it returns a
`DictionaryImportResult` containing both `destination` and `validation`.
`import_files()` remains the simpler path-only API.

Loading large Spylls dictionaries and checking MyThes indexes are synchronous
operations. Applications must run validation outside the Qt GUI thread.
