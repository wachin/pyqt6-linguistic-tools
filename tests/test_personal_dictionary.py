from __future__ import annotations

import json
import os
from pathlib import Path
import unicodedata

import pytest

from pyqt6_linguistic_tools import (
    PersonalDictionary,
    PersonalDictionaryError,
    PersonalDictionaryStore,
    normalize_personal_locale,
    normalize_personal_word,
)


@pytest.mark.parametrize("locale", ["../../escape", "es/EC", "es\\EC", "es:EC"])
def test_personal_dictionary_rejects_unsafe_locale_paths(locale: str, tmp_path: Path):
    with pytest.raises(ValueError, match="unsafe characters"):
        PersonalDictionary(locale, tmp_path)

    assert not tuple(tmp_path.iterdir())


def test_personal_locale_normalization_is_portable():
    assert normalize_personal_locale("ES-ec") == "es_EC"
    assert normalize_personal_locale("sr-Latn-RS") == "sr_Latn_RS"


def test_personal_dictionary_does_not_create_storage_until_mutated(tmp_path: Path):
    dictionary = PersonalDictionary("es-ec", tmp_path / "personal")

    assert dictionary.locale == "es_EC"
    assert dictionary.path == tmp_path / "personal" / "es_EC.json"
    assert dictionary.words() == ()
    assert not dictionary.root.exists()


def test_add_list_remove_and_clear_persist_utf8(tmp_path: Path):
    dictionary = PersonalDictionary("es_EC", tmp_path)

    assert dictionary.add_word("niño")
    assert not dictionary.add_word("niño")
    assert dictionary.add_words(("canción", "Ecuador")) == ("canción", "Ecuador")
    assert dictionary.words() == ("canción", "Ecuador", "niño")
    assert dictionary.contains("niño")
    assert not dictionary.contains("Niño")
    assert dictionary.contains("Niño", case_sensitive=False)

    raw = dictionary.path.read_bytes()
    assert "niño".encode() in raw
    assert b"\\u00f1" not in raw
    payload = json.loads(raw.decode("utf-8"))
    assert payload["version"] == 1
    assert payload["locale"] == "es_EC"

    assert dictionary.remove_word("Ecuador")
    assert not dictionary.remove_word("Ecuador")
    assert dictionary.clear()
    assert not dictionary.clear()
    assert PersonalDictionary("es_EC", tmp_path).words() == ()


def test_words_are_nfc_normalized_and_duplicates_are_collapsed(tmp_path: Path):
    dictionary = PersonalDictionary("es_EC", tmp_path)
    decomposed = unicodedata.normalize("NFD", "canción")

    assert dictionary.add_words((decomposed, "canción")) == ("canción",)
    assert dictionary.words() == ("canción",)
    assert normalize_personal_word(decomposed) == "canción"


@pytest.mark.parametrize("word", ["", "  ", "two words", "line\nbreak", "bad\x00word"])
def test_invalid_personal_words_are_rejected(word: str, tmp_path: Path):
    dictionary = PersonalDictionary("es_EC", tmp_path)

    with pytest.raises(ValueError):
        dictionary.add_word(word)
    assert not dictionary.path.exists()


def test_bulk_operations_reject_a_single_string_iterable(tmp_path: Path):
    dictionary = PersonalDictionary("es_EC", tmp_path)

    with pytest.raises(TypeError):
        dictionary.add_words("palabra")
    with pytest.raises(TypeError):
        dictionary.remove_words("palabra")


def test_two_instances_merge_updates_in_shared_storage(tmp_path: Path):
    chordflow = PersonalDictionary("es_EC", tmp_path)
    chordpages = PersonalDictionary("es_EC", tmp_path)

    assert chordflow.words() == ()
    chordflow.add_word("ChordFlow")
    chordpages.add_word("ChordPages")

    assert chordflow.words() == ("ChordFlow", "ChordPages")
    assert chordpages.words() == ("ChordFlow", "ChordPages")


def test_external_change_updates_revision_and_snapshot(tmp_path: Path):
    first = PersonalDictionary("es_EC", tmp_path)
    second = PersonalDictionary("es_EC", tmp_path)
    initial_revision = first.revision

    second.add_word("externa")

    assert first.words() == ("externa",)
    assert first.revision > initial_revision


def test_malformed_file_is_never_silently_overwritten(tmp_path: Path):
    path = tmp_path / "es_EC.json"
    path.write_text("{broken", encoding="utf-8")
    dictionary = PersonalDictionary("es_EC", tmp_path)

    with pytest.raises(PersonalDictionaryError) as captured:
        dictionary.add_word("segura")

    assert captured.value.path == path
    assert path.read_text(encoding="utf-8") == "{broken"


def test_locale_mismatch_is_rejected(tmp_path: Path):
    path = tmp_path / "es_EC.json"
    path.write_text(
        json.dumps({"version": 1, "locale": "es_ES", "words": ["hola"]}),
        encoding="utf-8",
    )

    with pytest.raises(PersonalDictionaryError):
        PersonalDictionary("es_EC", tmp_path).words()


def test_atomic_save_failure_preserves_previous_file(tmp_path: Path, monkeypatch):
    dictionary = PersonalDictionary("es_EC", tmp_path)
    dictionary.add_word("original")
    original = dictionary.path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(PersonalDictionaryError):
        dictionary.add_word("nuevo")

    assert dictionary.path.read_bytes() == original
    assert dictionary.words() == ("original",)
    assert not tuple(tmp_path.glob("*.tmp"))


def test_stale_lock_is_recovered_but_live_lock_times_out(tmp_path: Path):
    dictionary = PersonalDictionary(
        "es_EC",
        tmp_path,
        lock_timeout=0.01,
        stale_lock_seconds=1,
    )
    tmp_path.mkdir(exist_ok=True)
    dictionary._lock_path.write_text("stale", encoding="ascii")
    os.utime(dictionary._lock_path, (0, 0))

    assert dictionary.add_word("recuperada")

    dictionary._lock_path.write_text("live", encoding="ascii")
    with pytest.raises(PersonalDictionaryError, match="timed out"):
        dictionary.add_word("bloqueada")
    dictionary._lock_path.unlink()


def test_store_wide_lock_coordinates_mutations_across_locales(tmp_path: Path):
    dictionary = PersonalDictionary(
        "en_US",
        tmp_path,
        lock_timeout=0.01,
        stale_lock_seconds=1,
    )
    tmp_path.mkdir(exist_ok=True)
    dictionary._store_lock_path.write_text("live", encoding="ascii")

    with pytest.raises(PersonalDictionaryError, match="store lock"):
        dictionary.add_word("blocked")

    os.utime(dictionary._store_lock_path, (0, 0))
    assert dictionary.add_word("recovered")


def test_store_supports_application_specific_and_explicitly_shared_roots(tmp_path: Path):
    application_a = PersonalDictionaryStore(tmp_path / "app-a")
    application_b = PersonalDictionaryStore(tmp_path / "app-b")
    shared_a = PersonalDictionaryStore(tmp_path / "shared")
    shared_b = PersonalDictionaryStore(tmp_path / "shared")

    application_a.for_locale("es_EC").add_word("privada")
    assert application_b.for_locale("es_EC").words() == ()

    shared_a.for_locale("es_EC").add_word("compartida")
    assert shared_b.for_locale("es_EC").contains("compartida")
    assert shared_b.available_locales() == ("es_EC",)
