# Portable engine baseline

Baseline captured on 2026-08-20 with Python 3.13.5 and pytest 8.3.5.

## Spylls

- Maintained fork: `https://github.com/wachin/spylls.git`
- Pinned commit: `9a0d201c4c375ef02205164013c1650980f7dad1`
- Original project: `https://github.com/zverok/spylls`
- Version declared by packaging: `0.1.7`
- License file: Mozilla Public License 2.0.

There is a metadata inconsistency to resolve before publishing: `setup.py`
classifies Spylls as MIT while the repository's `LICENSE` contains MPL-2.0.
The license file is treated as authoritative until provenance is reviewed; no
license metadata has been changed speculatively.

`python -m pytest -q` does not provide a usable upstream baseline. Collection
fails because draft unit tests import the obsolete package name `spyll` and one
file contains invalid Python syntax. The upstream `tests/README.rst` identifies
the integration scripts as the working suite. Executed against the local source
with `PYTHONPATH=.`:

- Lookup: 107 scenarios; 101 active passed, 6 explicitly pending, 0 failed.
- Suggest: 34 scenarios; 31 active passed, 3 explicitly pending, 0 failed.

The repository-level corpus tests add real LibreOffice dictionaries for UTF-8,
ISO-8859-1, ISO-8859-2, ISO-8859-7, ISO-8859-13 and ISO-8859-15.

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

## Fork policy

Engine behavior changes belong in the corresponding engine fork and require a
regression test plus a changelog entry. Stable engine commits are then pinned by
the parent repository. Upstream updates must be merged deliberately and the
complete engine and corpus suites rerun before advancing the pin. Small,
focused fixes should be suitable for proposing to the original project when
its contribution channel is available.
