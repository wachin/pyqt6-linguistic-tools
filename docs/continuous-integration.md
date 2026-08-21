# Continuous integration

The toolkit keeps fast cross-platform checks separate from the large
LibreOffice dictionary corpus. Both workflows are deliberately manual-only to
avoid consuming GitHub Actions minutes, artifact storage, or notification
quota when commits and pull requests are created. A push, pull request, tag,
or schedule does not start either workflow.

## Fast CI

`.github/workflows/ci.yml` runs only when a repository user selects
**Actions → Fast CI → Run workflow**. Its compact matrix covers:

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

An independent typing job installs the `typing` and `qt` extras and runs
`python -m mypy`. The checked target is the complete core and Qt implementation
under the Python 3.10 language contract. Missing third-party annotations are
ignored, but toolkit errors, unused suppressions, redundant casts, and typed or
untyped function bodies remain checked. No toolkit package is excluded.

A separate Ubuntu job installs the distribution's `hunspell-es` and
`mythes-es` data packages, then runs the Linux platform smoke tests. Installing
these packages is an action performed only inside the disposable CI runner;
the toolkit itself never invokes a package manager or requests privileges.

## Corpus CI

`.github/workflows/corpus.yml` checks out
`wachin/libreoffice-dictionaries-collection` into an explicit test-data
directory. It never hard-codes a GuitarChordStudio checkout path.

The GitHub Actions **Run workflow** form allows the user to choose `curated` or
`full`. Curated tests run on Ubuntu, Windows, and macOS; the full corpus runs on
Ubuntu. Neither suite runs automatically. Every corpus job runs the
deterministic fast suite first, so a specialized job never replaces the shared
engine and Qt contracts.

Both suites produce JUnit XML locally in the disposable runner. The
`upload_reports` input defaults to `false`, so no artifact storage is consumed
unless the user explicitly enables it before starting the workflow. Enabled
artifacts are retained for three days, including when pytest fails. These files
are machine-readable test results, not the planned locale-by-locale dictionary
compatibility report; that richer report remains a separate roadmap item and
must follow the same explicit upload policy.

## Required checks and releases

Workflow failures make manually requested jobs fail, but they do not run as
required checks on every commit. This repository currently has no release
automation. Any future release workflow must use `workflow_dispatch` only and
must never publish a release because of a push, tag, pull request, schedule, or
successful CI run. The repository user must explicitly request every release.

Static typing is a normal failing CI job. In particular, Qt return values that
its bindings declare as optional are checked before use, and toolkit widget
properties must not override Qt methods with incompatible return types.
