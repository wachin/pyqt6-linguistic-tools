"""Tests for the dictionary catalog shipped with the toolkit."""

from __future__ import annotations

from importlib.resources import files

from pyqt6_linguistic_tools import (
    BUNDLED_CATALOG_PATH,
    load_bundled_dictionary_catalog,
    load_dictionary_catalog,
)


def test_bundled_catalog_is_packaged() -> None:
    resource = files("pyqt6_linguistic_tools").joinpath("data").joinpath(
        "dictionaries.json"
    )

    assert resource.is_file()
    assert BUNDLED_CATALOG_PATH.is_file()


def test_bundled_catalog_matches_the_packaged_file() -> None:
    bundled = load_bundled_dictionary_catalog()
    explicit = load_dictionary_catalog(BUNDLED_CATALOG_PATH)

    assert bundled == explicit


def test_bundled_catalog_contains_the_spanish_bundle() -> None:
    catalog = load_bundled_dictionary_catalog()

    assert len(catalog.dictionaries) == 57
    assert "v1.0-dictionaries-thesaurus" in catalog.source

    spanish = catalog.get("es")
    assert spanish is not None
    assert spanish.name == "Spanish"
    assert spanish.url.endswith("/dict-es.tar.gz")
    assert spanish.size == 6646323
    assert spanish.sha256 is None
    assert not catalog.supports_verified_downloads
