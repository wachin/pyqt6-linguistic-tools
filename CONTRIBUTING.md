# Contributing

## Scope

The portable Spylls and PyThes engines are stabilized before adding the public
backend and Qt layers. Native Hunspell and MyThes integrations are postponed
until the portable release works correctly on Linux, Windows, and macOS.

## Changes to engine forks

Use a short-lived branch such as `fix/bom-encoding` in the corresponding fork.
Every behavior fix requires a focused regression test and an entry in that
fork's changelog. Keep the maintained default branch releasable; after its
tests pass, update the pinned submodule commit in this repository.

When reviewing a new upstream revision, merge it on a dedicated
`sync/upstream-<version>` branch and run both the engine's own suite and this
repository's corpus suite. Do not discard maintained regressions or modify a
source dictionary to conceal an incompatibility.

## Tests

Run the fast suite on every change:

```bash
python -m pytest -m 'not corpus'
```

Run real dictionary compatibility tests by setting
`LIBREOFFICE_DICTIONARIES_PATH` or passing `--dictionary-corpus`. Corpus files
are external test inputs and retain their original licenses and encodings.
Use `-m 'corpus and not full_corpus'` for the curated pull-request suite and
`-m full_corpus` for the scheduled/manual pass.
