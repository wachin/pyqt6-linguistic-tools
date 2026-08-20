# Portable engine baseline

Baseline captured on 2026-08-20 with Python 3.13.5 and pytest 8.3.5.

## Spylls

- Maintained fork: `https://github.com/wachin/spylls.git`
- Pinned commit: `9a0d201c4c375ef02205164013c1650980f7dad1`
- Original project: `https://github.com/zverok/spylls`
- Version declared by packaging: `0.1.7`
- License file: Mozilla Public License 2.0.

The baseline contained two metadata inconsistencies: `setup.py` classified
Spylls as MIT while the changelog and `LICENSE` record the change to MPL-2.0,
and the runtime exposed version 0.1.0 while packaging declared 0.1.7. The
maintained fork now aligns both values with the repository evidence and tests
them automatically.

`python -m pytest -q` does not provide a usable upstream baseline. Collection
fails because draft unit tests import the obsolete package name `spyll` and one
file contains invalid Python syntax. The upstream `tests/README.rst` identifies
the integration scripts as the working suite. Executed against the local source
with `PYTHONPATH=.`:

- Lookup baseline: 107 scenarios; 101 active passed, 6 explicitly pending, 0
  failed. After completing `CHECKCOMPOUNDPATTERN` replacement and zero-pattern
  behavior plus `ONLYINCOMPOUND` linking-affix boundaries: 105 active passed,
  2 explicitly pending, 0 failed.
- Suggest: 34 scenarios; 31 active passed, 3 explicitly pending, 0 failed.

The maintained fork wraps both historical scripts with pytest. The wrapper
requires their exact active/pending totals and zero failures, so regressions
now produce a failing process suitable for CI. Its initial directive inventory
is maintained in `docs/hunspell-compatibility.md` inside the Spylls fork.

The repository-level corpus tests add real LibreOffice dictionaries for UTF-8,
ISO-8859-1, ISO-8859-2, ISO-8859-7, ISO-8859-13 and ISO-8859-15.

The maintained fork now also provides an encoding-agnostic directive scanner.
Against the 88 LibreOffice `.aff` files it initially classified 47 directive
names as supported, 9 as partial, 8 as non-spelling metadata/extensions, and
one `SFT` line in the Mongolian dictionary as probable source corruption.
`FULLSTRIP` was then implemented for both prefix and suffix lookup.
`CHECKCOMPOUNDPATTERN` now covers boundary rejection, replacements, flag
conditions, and the special `0` unmodified-stem form. These changes move the
current count to 49 supported and 7 partial directives. All nine real
LibreOffice dictionaries that enable `FULLSTRIP` and all 20 that enable
`ONLYINCOMPOUND` load and accept sampled stems.
`WORDCHARS`, although more widespread, belongs to the toolkit tokenizer rather
than dictionary lookup.

## PyThes

- Maintained fork: `https://github.com/wachin/pythes.git`
- Pinned commit before stabilization changes:
  `3fa9c8812c417d23be51082d1f06e3d9a6dd44c5`
- Original project: `https://github.com/corerd/pythes`
- Version declared by packaging: `1.0.0`
- License: MIT.

The fork initially had no automated tests. The first complete pass through the
26 LibreOffice thesaurus data files found:

- A UTF-8 BOM rejected in the Russian data and index files.
- A malformed duplicate line without a byte offset in the Polish index.
- Declared index-count mismatches in two German variants.

The initial stabilization patch adds regression tests, accepts the BOM, warns
about malformed indexes, and reconstructs an unusable index in memory from the
original data file. It never rewrites a source dictionary. After the patch all
26 thesauri load and return at least one indexed entry; known recoveries remain
visible as warnings.

External indexes are now checked completely at load time: the declared count
must be valid and every byte offset must point to the named `.dat` entry.
Missing, truncated, malformed, and stale indexes are rebuilt in memory. The
rebuild supports LF and CRLF source files and can skip isolated malformed data
headers with a warning. This exposed the known stray `technika` line and stale
`metodologia` offset in the Polish corpus without modifying either source file.
All 26 corpus thesauri still pass after recovery.

PyThes now also exposes explicit `.idx` regeneration. It calculates offsets
from the source file in binary mode, preserves the encoding declaration, BOM,
and line endings, validates the temporary result, and publishes it atomically.
Existing files require `overwrite=True`. A scheduled corpus test regenerates
all 26 indexes into temporary storage and validates lookups without writing to
the LibreOffice collection.

Index keys and lookup input now share NFC normalization, so precomposed and
combining-mark spellings resolve consistently without rewriting dictionary
content. Repeated lookups use a per-instance, thread-safe LRU cache bounded to
256 entries by default; misses are cached too, zero disables it, and explicit
clearing or index regeneration invalidates stored results. All 26 corpus
thesauri continue to pass with normalization and caching enabled.

## Fork policy

Engine behavior changes belong in the corresponding engine fork and require a
regression test plus a changelog entry. Stable engine commits are then pinned by
the parent repository. Upstream updates must be merged deliberately and the
complete engine and corpus suites rerun before advancing the pin. Small,
focused fixes should be suitable for proposing to the original project when
its contribution channel is available.
