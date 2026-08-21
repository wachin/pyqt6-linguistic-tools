# Continuous integration

The toolkit keeps fast cross-platform checks separate from the large
LibreOffice dictionary corpus. This makes ordinary commits inexpensive while
preserving real dictionary coverage before changes are merged.

## Fast CI

`.github/workflows/ci.yml` runs on pushes, pull requests, and manual dispatches.
Its compact matrix covers:

- Ubuntu 24.04 with Python 3.10, the minimum supported version;
- Ubuntu 24.04 with Python 3.14;
- the current GitHub-hosted Windows image with Python 3.14;
- the current GitHub-hosted macOS image with Python 3.14.

Every matrix entry initializes only the Spylls and PyThes submodules. Hunspell,
MyThes, and Sonnet source-reference submodules are deliberately excluded from
runtime CI. The job installs the toolkit's `test` and `qt` extras and runs:

```bash
python -m pytest -m "not corpus and not platform"
```

Qt uses the offscreen platform so tests do not open windows. The fast suite
already contains backend loading, Unicode, UTF-16 offsets, and small UTF-8 and
legacy-encoding regression fixtures.

A separate Ubuntu job installs the distribution's `hunspell-es` and
`mythes-es` data packages, then runs the Linux platform smoke tests. Installing
these packages is an action performed only inside the disposable CI runner;
the toolkit itself never invokes a package manager or requests privileges.

## Corpus CI

`.github/workflows/corpus.yml` checks out
`wachin/libreoffice-dictionaries-collection` into an explicit test-data
directory. It never hard-codes a GuitarChordStudio checkout path.

Pull requests run the curated corpus tests on Ubuntu, Windows, and macOS. The
full corpus runs on Ubuntu every Sunday and can also be selected from the
GitHub Actions **Run workflow** form. A manual dispatch can choose `curated` or
`full`. Every corpus and platform job runs the deterministic fast suite first,
so a specialized job never replaces the shared engine and Qt contracts.

Both suites produce JUnit XML and upload it even when pytest fails. These files
are machine-readable test results, not the planned locale-by-locale dictionary
compatibility report; that richer report remains a separate roadmap item.

## Required checks and releases

Workflow failures make their jobs fail, but repository policy determines
whether merging or releasing is blocked. Once the first remote runs are green,
configure branch protection for `main` and require the relevant Fast CI and
curated-corpus checks. A future release workflow must depend on those checks;
this repository currently has no release automation to gate.

The static typing job is intentionally not enabled yet. `mypy` currently
identifies genuine annotations and Qt override issues. Those should be fixed
incrementally instead of suppressing the entire Qt package or allowing the CI
step to succeed on errors.
