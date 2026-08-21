from __future__ import annotations

from pathlib import Path

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    LinuxSystemDictionaryProvider,
)


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_linux_provider_combines_existing_roots_and_ignores_missing_ones(
    tmp_path: Path,
):
    hunspell = tmp_path / "hunspell"
    mythes = tmp_path / "mythes"
    _write(hunspell / "es_EC.aff", "SET UTF-8\n")
    _write(hunspell / "es_EC.dic", "1\nEcuador\n")
    _write(mythes / "th_es_EC_v2.dat", "UTF-8\n")
    _write(mythes / "th_es_EC_v2.idx", "UTF-8\n0\n")
    provider = LinuxSystemDictionaryProvider(
        (hunspell, tmp_path / "missing", mythes)
    )

    info = DictionaryRegistry((provider,)).get("es_EC")

    assert info is not None
    assert info.has_spelling and info.has_thesaurus
    assert info.spelling_source == "system"
    assert info.thesaurus_source == "system"
    assert provider.priority == DictionarySourcePriority.SYSTEM
    assert not (tmp_path / "missing").exists()


def test_linux_provider_is_read_only_by_contract(tmp_path: Path):
    provider = LinuxSystemDictionaryProvider(tmp_path / "missing")

    assert provider.discover() == ()
    assert not provider.roots[0].exists()
    assert not hasattr(provider, "ensure_directory")
    assert not hasattr(provider, "import_files")
    assert not hasattr(provider, "remove_bundle")
