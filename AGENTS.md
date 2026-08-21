# Agent instructions for pyqt6-linguistic-tools

This repository owns reusable linguistic functionality. It must remain usable
outside GuitarChordStudio and must not import GuitarChordStudio code or
hard-code paths from a parent checkout.

## Required architecture

- Use Spylls and PyThes as the portable initial backends on every platform.
- Linux system providers discover dictionary data files; they do not require
  or invoke native Hunspell/MyThes libraries.
- Keep backend contracts, providers/registry, service logic, and the optional
  Qt integration separate. Core imports must work without PyQt6 installed.
- Keep platform-specific discovery inside providers and host-specific token
  rules behind `TokenFilter`.
- Official dictionaries are immutable. Store personal and ignored words in
  their dedicated layers.
- Native engines and Sonnet are reference or optional post-1.0 work, not
  runtime dependencies.

## Change requirements

- Support Python 3.10 and run `python3 -m mypy` for all source changes.
- Add focused tests for behavior changes. Engine compatibility fixes require a
  regression test in the affected Spylls/PyThes fork before the fix.
- Keep corpus locations configurable through pytest options, environment
  variables, or explicit API/CLI parameters.
- Preserve deterministic output and relative paths in machine-readable test
  artifacts.
- Update `CHANGELOG.md` plus relevant README/docs when public behavior,
  commands, packaging, or CI changes.
- Do not mark roadmap work complete until its tests and documented acceptance
  criteria have actually run.
- Keep GitHub Actions manual-only. Do not add `push`, `pull_request`,
  `schedule`, or tag-driven workflow triggers. Artifact uploads must be an
  explicit user choice with short retention, and any future release workflow
  must require `workflow_dispatch` rather than publishing automatically.

## Validation

The normal local gate is:

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -c pyproject.toml -q \
  -m 'not corpus and not platform'
python3 -m mypy
git diff --check
```

See `docs/testing.md` for corpus/platform commands and
`docs/continuous-integration.md` for workflow responsibilities. Full-corpus
tests are intentionally expensive; use focused or curated tests while
iterating.

This repository is a Git submodule. Commit it before committing the updated
pointer in its parent. Nested Spylls/PyThes changes must be committed first on
their `master` branches.
