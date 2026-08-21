# Deprecation policy

This document describes how `pyqt6-linguistic-tools` manages API changes during
the `0.x` development phase and after the `1.0.0` stable release.

## During 0.x (pre-1.0)

The major version is zero while the API stabilises. During this phase:

- **Breaking changes are allowed** but must be documented in `CHANGELOG.md`.
- Deprecated names emit a `DeprecationWarning` for at least one minor release
  before removal.
- The deprecation warning includes the recommended replacement.
- Backward-compatible re-exports may be kept indefinitely when the maintenance
  cost is low.

## After 1.0.0

After the first stable release, the public API documented in
[`public-api.md`](public-api.md) follows Semantic Versioning 2.0:

- **Patch** (`1.0.0` → `1.0.1`): backward-compatible bug fixes.
- **Minor** (`1.0.0` → `1.1.0`): new features; existing code continues to
  work.
- **Major** (`1.0.0` → `2.0.0`): breaking changes to the public API.

### Deprecation cycle (post-1.0)

1. The deprecated name is marked with a `DeprecationWarning` in a minor
   release.
2. The warning identifies the recommended replacement.
3. After at least **two minor releases** (or **six months**, whichever is
   longer), the deprecated name may be removed in the next major release.

### What is not part of the public API

Names not listed in [`public-api.md`](public-api.md) are implementation
details. They may change at any time without a deprecation cycle. This
includes:

- Modules whose names begin with `_`.
- Classes, functions, and constants not exported from `pyqt6_linguistic_tools`
  or `pyqt6_linguistic_tools.qt`.
- Test utilities and test-only exports.

## Reporting a deprecation

Use `warnings.warn()` with `DeprecationWarning` and a clear message:

```python
import warnings
warnings.warn(
    "SpyllsBackend is deprecated, use LinguisticService instead",
    DeprecationWarning,
    stacklevel=2,
)
```

## Current deprecations

None at this time.