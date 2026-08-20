from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    DictionaryCatalogError,
    DictionaryImportError,
    DictionaryRegistry,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
    application_data_directory,
    dictionary_storage_paths,
    load_dictionary_catalog,
)


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_storage_paths_are_shared_and_do_not_create_directories(tmp_path: Path):
    paths = dictionary_storage_paths("GuitarChordStudio", base_path=tmp_path)

    assert paths.root == tmp_path / "GuitarChordStudio" / "dictionaries"
    assert paths.managed == paths.root / "managed"
    assert paths.user == paths.root / "user"
    assert not paths.root.exists()
    assert application_data_directory(
        "GuitarChordStudio", base_path=tmp_path
    ) == tmp_path / "GuitarChordStudio"


@pytest.mark.parametrize("namespace", ["", ".", "..", "bad/name", "bad\\name"])
def test_storage_rejects_unsafe_namespaces(namespace: str):
    with pytest.raises(ValueError):
        application_data_directory(namespace)


def test_managed_and_user_providers_treat_missing_roots_as_empty(tmp_path: Path):
    managed = ManagedDictionaryProvider(tmp_path / "managed")
    user = UserDictionaryProvider(tmp_path / "user")

    assert managed.discover() == ()
    assert user.discover() == ()
    assert not managed.root.exists()
    assert not user.root.exists()
    assert managed.ensure_directory() == managed.root
    assert user.ensure_directory() == user.root


def test_manual_import_publishes_complete_bundle_atomically(tmp_path: Path):
    source = tmp_path / "source"
    aff = _write(source / "es_EC.aff", "SET UTF-8\n")
    dic = _write(source / "es_EC.dic", "1\nEcuador\n")
    dat = _write(
        source / "th_es_v2.dat",
        "ISO8859-1\nfeliz|1\n-|dichoso|contento\n",
    )
    idx = _write(source / "th_es_v2.idx", "ISO8859-1\n1\nfeliz|10\n")
    provider = UserDictionaryProvider(tmp_path / "user")

    destination = provider.import_files(
        [aff, dic, dat, idx],
        bundle_name="spanish-ecuador",
    )

    assert destination == provider.root / "spanish-ecuador"
    assert {path.name for path in destination.iterdir()} == {
        "es_EC.aff",
        "es_EC.dic",
        "th_es_v2.dat",
        "th_es_v2.idx",
    }
    assert not any(path.name.startswith(".import-") for path in provider.root.iterdir())
    info = DictionaryRegistry((provider,)).get("es_EC")
    assert info is not None
    assert info.has_spelling and info.has_thesaurus
    assert info.spelling_source == "user"
    assert info.thesaurus_source == "user"


def test_manual_import_refuses_incomplete_or_existing_bundle(tmp_path: Path):
    source = tmp_path / "source"
    aff = _write(source / "es_EC.aff", "SET UTF-8\n")
    dic = _write(source / "es_EC.dic", "1\nEcuador\n")
    provider = UserDictionaryProvider(tmp_path / "user")

    with pytest.raises(DictionaryImportError, match="complete Hunspell"):
        provider.import_files([aff])
    assert not any(provider.root.iterdir())

    provider.import_files([aff, dic], bundle_name="es_EC")
    with pytest.raises(FileExistsError):
        provider.import_files([aff, dic], bundle_name="es_EC")
    assert not any(path.name.startswith(".import-") for path in provider.root.iterdir())


def test_catalog_validates_entries_and_normalizes_lookup(tmp_path: Path):
    catalog_path = tmp_path / "dictionaries.json"
    catalog_path.write_text(
        json.dumps(
            {
                "source": "example/release",
                "dictionaries": [
                    {
                        "code": "pt-BR",
                        "name": "Portuguese (Brazil)",
                        "url": "https://example.test/dict-pt-BR.tar.gz",
                        "size": 123,
                        "sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    catalog = load_dictionary_catalog(catalog_path)

    assert catalog.get("pt_BR").name == "Portuguese (Brazil)"
    assert catalog.get("missing") is None
    assert catalog.supports_verified_downloads


@pytest.mark.parametrize(
    "entry",
    [
        {"code": "../es", "name": "Spanish", "url": "https://example/es", "size": 1},
        {"code": "es", "name": "", "url": "https://example/es", "size": 1},
        {"code": "es", "name": "Spanish", "url": "http://example/es", "size": 1},
        {"code": "es", "name": "Spanish", "url": "https://example/es", "size": True},
        {
            "code": "es",
            "name": "Spanish",
            "url": "https://example/es",
            "size": 1,
            "sha256": "invalid",
        },
    ],
)
def test_catalog_rejects_unsafe_or_malformed_entries(tmp_path: Path, entry: dict):
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps({"source": "example", "dictionaries": [entry]}),
        encoding="utf-8",
    )

    with pytest.raises(DictionaryCatalogError):
        load_dictionary_catalog(path)
