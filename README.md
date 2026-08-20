# PyQt6 Linguistic Tools

Reusable linguistic infrastructure for Python and PyQt6 applications. The
project will provide a single cross-platform API for spell checking, spelling
suggestions, and synonyms.

Development is currently focused on stabilizing its portable engines:

- [Spylls](https://github.com/zverok/spylls), for Hunspell dictionaries.
- [PyThes](https://github.com/corerd/pythes), for MyThes thesauri.

Native Hunspell and MyThes are outside the scope of this first stage. They may
be added later as optional backends without changing the public API.

## Setting up the repository

```bash
git submodule update --init --recursive
python -m pip install -e '.[test]'
python -m pytest
```

The fast tests do not require external dictionary downloads. The compatibility
suite uses an explicitly configured LibreOffice dictionary collection:

```bash
LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts \
  python -m pytest -m 'corpus and not full_corpus'
```

The corpus can also be selected with a command-line option:

```bash
python -m pytest -m 'corpus and not full_corpus' \
  --dictionary-corpus=/path/to/dicts
```

The full thesaurus pass is reserved for manual or scheduled execution:

```bash
python -m pytest -m full_corpus --dictionary-corpus=/path/to/dicts
```

The corpus path is never embedded in the package. See
[`docs/engine-baseline.md`](docs/engine-baseline.md) for the verified initial
engine status.
