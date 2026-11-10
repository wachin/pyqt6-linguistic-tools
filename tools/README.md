# Tools

## fetch-dict-list.py

Generate the dictionary download catalog that ships with the package.

```bash
python3 tools/fetch-dict-list.py --tag v1.0-dictionaries-thesaurus
```

By default it writes `src/pyqt6_linguistic_tools/data/dictionaries.json`, which
`load_bundled_dictionary_catalog()` loads and includes in wheels and source
distributions. Use `--output` to write a different file, or
`load_dictionary_catalog(path)` in a host application that maintains its own
catalog.

When GitHub exposes an asset digest, the generator adds the corresponding
`sha256` field. The loader validates the checksum format and the Dictionary
Manager enables Download only for entries with a checksum.

The generator performs network access and is intentionally manual-only; it is
not part of the test suite or CI.
