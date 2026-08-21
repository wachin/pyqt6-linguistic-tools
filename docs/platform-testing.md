# Platform testing

The platform matrix records only environments that have actually executed the
relevant tests. Passing on one Linux distribution does not claim coverage for
Ubuntu, Windows, or macOS.

## Linux system-resource smoke test

Run the focused matrix with:

```bash
python -m pytest -m platform
```

`tests/platform/test_linux_system_dictionaries.py` requires Linux plus complete
`es_EC` Hunspell and MyThes data in the conventional system directories. It
skips with an explicit reason when those resources are absent, so minimal CI
images remain valid rather than reporting a false failure.

The smoke test verifies all of the following through the public service:

- discovery of the installed `es_EC.aff/.dic` and `th_es_EC_v2.dat/.idx`;
- spelling, rejection of an invented misspelling, and suggestions;
- a real Spanish synonym lookup;
- selection of `spylls` and `pythes` as the two backends;
- no new import of Python bindings named `hunspell` or `mythes`.

The last check demonstrates that installed dictionary files and installed
native engines are independent. It does not claim that native shared libraries
are absent from the test machine. A separate execution on a machine or image
without those libraries is required before checking that matrix item.

## Portable provider tests

`tests/test_linux_system_provider.py` uses temporary directories on every
operating system. It verifies multi-root discovery, absent-directory handling,
source priority, and the provider's read-only API without depending on Linux
packages. These tests remain part of the normal fast suite.

Future Windows and macOS jobs should reuse the backend and service contracts,
then add platform smoke tests for virtual environments and packaged
applications. Matrix entries should be checked only after their corresponding
job or documented manual run succeeds.
