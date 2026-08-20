from __future__ import annotations

import json
import os
from pathlib import Path
import unicodedata

import pytest

from pyqt6_linguistic_tools import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    PersonalDictionaryBackupError,
    PersonalDictionaryBackupManager,
    PersonalDictionaryStore,
)


def _manager(root: Path) -> PersonalDictionaryBackupManager:
    return PersonalDictionaryBackupManager(PersonalDictionaryStore(root))


def test_export_all_and_inspect_utf8_preview(tmp_path: Path):
    store = PersonalDictionaryStore(tmp_path / "personal")
    store.for_locale("es_EC").add_words(("niño", "canción"))
    store.for_locale("en_US").add_word("ChordFlow")
    destination = tmp_path / "all.ptlbackup"

    preview = PersonalDictionaryBackupManager(store).export(destination)

    assert preview.path == destination
    assert preview.version == BACKUP_VERSION
    assert preview.locales == ("en_US", "es_EC")
    assert preview.total_words == 3
    assert preview.word_count("es-ec") == 2
    assert "niño".encode("utf-8") in destination.read_bytes()
    assert b"\\u00f1" not in destination.read_bytes()

    inspected = PersonalDictionaryBackupManager(store).inspect(destination)
    assert inspected == preview
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["format"] == BACKUP_FORMAT
    assert payload["version"] == BACKUP_VERSION


def test_export_selected_locale_including_an_empty_dictionary(tmp_path: Path):
    manager = _manager(tmp_path / "personal")

    preview = manager.export(
        tmp_path / "selected.ptlbackup", locales=("es-ec",)
    )

    assert preview.locales == ("es_EC",)
    assert preview.total_words == 0


def test_export_does_not_overwrite_without_explicit_permission(tmp_path: Path):
    manager = _manager(tmp_path / "personal")
    destination = tmp_path / "backup.ptlbackup"
    destination.write_bytes(b"original")

    with pytest.raises(PersonalDictionaryBackupError) as captured:
        manager.export(destination)

    assert captured.value.operation == "export"
    assert destination.read_bytes() == b"original"


def test_export_overwrite_is_atomic_on_failure(tmp_path: Path, monkeypatch):
    manager = _manager(tmp_path / "personal")
    destination = tmp_path / "backup.ptlbackup"
    destination.write_bytes(b"original")

    def fail_replace(source, target):
        raise OSError("simulated export failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(PersonalDictionaryBackupError):
        manager.export(destination, overwrite=True)

    assert destination.read_bytes() == b"original"
    assert not tuple(tmp_path.glob("*.tmp"))


def test_backup_destination_cannot_be_inside_personal_store(tmp_path: Path):
    root = tmp_path / "personal"
    manager = _manager(root)

    with pytest.raises(PersonalDictionaryBackupError, match="outside"):
        manager.export(root / "backup.ptlbackup")


def test_merge_preserves_existing_words_and_removes_duplicates(tmp_path: Path):
    source = PersonalDictionaryStore(tmp_path / "source")
    decomposed = unicodedata.normalize("NFD", "canción")
    source.for_locale("es_EC").add_words((decomposed, "nueva"))
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)

    target = PersonalDictionaryStore(tmp_path / "target")
    target.for_locale("es_EC").add_words(("canción", "existente"))
    result = PersonalDictionaryBackupManager(target).restore(backup, mode="merge")

    assert result.mode == "merge"
    assert result.locales == ("es_EC",)
    assert result.entries[0].previous_count == 2
    assert result.entries[0].backup_count == 2
    assert result.entries[0].final_count == 3
    assert result.entries[0].added_count == 1
    assert target.for_locale("es_EC").words() == (
        "canción",
        "existente",
        "nueva",
    )


def test_replace_changes_only_selected_personal_dictionaries(tmp_path: Path):
    source = PersonalDictionaryStore(tmp_path / "source")
    source.for_locale("es_EC").add_word("respaldo-es")
    source.for_locale("en_US").add_word("backup-en")
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)

    target = PersonalDictionaryStore(tmp_path / "target")
    target.for_locale("es_EC").add_word("anterior-es")
    target.for_locale("en_US").add_word("previous-en")

    result = PersonalDictionaryBackupManager(target).restore(
        backup, mode="replace", locales=("es-EC",)
    )

    assert result.locales == ("es_EC",)
    assert target.for_locale("es_EC").words() == ("respaldo-es",)
    assert target.for_locale("en_US").words() == ("previous-en",)


def test_inspection_accepts_utf8_bom_and_windows_line_endings(tmp_path: Path):
    backup = tmp_path / "portable.ptlbackup"
    payload = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "dictionaries": [{"locale": "es-EC", "words": ["niño"]}],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    backup.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    preview = _manager(tmp_path / "personal").inspect(backup)

    assert preview.locales == ("es_EC",)
    assert preview.entries[0].words == ("niño",)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"format": BACKUP_FORMAT, "version": 99, "dictionaries": []},
        {"format": BACKUP_FORMAT, "version": 1, "dictionaries": "bad"},
        {
            "format": BACKUP_FORMAT,
            "version": 1,
            "dictionaries": [{"locale": "../../escape", "words": ["bad"]}],
        },
        {
            "format": BACKUP_FORMAT,
            "version": 1,
            "dictionaries": [
                {"locale": "es-EC", "words": []},
                {"locale": "es_EC", "words": []},
            ],
        },
        {
            "format": BACKUP_FORMAT,
            "version": 1,
            "dictionaries": [{"locale": "es_EC", "words": ["two words"]}],
        },
    ],
)
def test_malformed_backups_are_rejected_before_local_changes(
    payload, tmp_path: Path
):
    backup = tmp_path / "malformed.ptlbackup"
    backup.write_text(json.dumps(payload), encoding="utf-8")
    target = PersonalDictionaryStore(tmp_path / "target")
    dictionary = target.for_locale("es_EC")
    dictionary.add_word("intacta")
    original = dictionary.path.read_bytes()

    with pytest.raises(PersonalDictionaryBackupError) as captured:
        PersonalDictionaryBackupManager(target).restore(backup)

    assert captured.value.operation == "inspect"
    assert dictionary.path.read_bytes() == original


def test_missing_selected_locale_is_rejected_before_local_changes(tmp_path: Path):
    source = PersonalDictionaryStore(tmp_path / "source")
    source.for_locale("es_EC").add_word("hola")
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)
    target = PersonalDictionaryStore(tmp_path / "target")

    with pytest.raises(PersonalDictionaryBackupError, match="does not contain"):
        PersonalDictionaryBackupManager(target).restore(
            backup, locales=("en_US",)
        )

    assert not target.root.exists()


def test_publish_failure_rolls_back_every_changed_locale(tmp_path: Path, monkeypatch):
    source = PersonalDictionaryStore(tmp_path / "source")
    source.for_locale("en_US").add_word("new-en")
    source.for_locale("es_EC").add_word("nuevo-es")
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)

    target = PersonalDictionaryStore(tmp_path / "target")
    target.for_locale("en_US").add_word("old-en")
    target.for_locale("es_EC").add_word("anterior-es")
    originals = {
        locale: target.for_locale(locale).path.read_bytes()
        for locale in ("en_US", "es_EC")
    }

    real_replace = os.replace
    failed = False

    def fail_second_restore(source_path, target_path):
        nonlocal failed
        source_path = Path(source_path)
        target_path = Path(target_path)
        if (
            not failed
            and ".restore." in source_path.name
            and target_path.name == "es_EC.json"
        ):
            failed = True
            raise OSError("simulated second-locale failure")
        return real_replace(source_path, target_path)

    monkeypatch.setattr(os, "replace", fail_second_restore)
    with pytest.raises(PersonalDictionaryBackupError, match="cannot publish"):
        PersonalDictionaryBackupManager(target).restore(backup, mode="replace")

    assert failed
    for locale, original in originals.items():
        assert target.for_locale(locale).path.read_bytes() == original
    assert not tuple(target.root.glob("*.tmp"))


def test_publish_failure_removes_a_newly_created_locale(tmp_path: Path, monkeypatch):
    source = PersonalDictionaryStore(tmp_path / "source")
    source.for_locale("en_US").add_word("new-en")
    source.for_locale("es_EC").add_word("nuevo-es")
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)
    target = PersonalDictionaryStore(tmp_path / "target")
    target.for_locale("es_EC").add_word("anterior-es")
    original_spanish = target.for_locale("es_EC").path.read_bytes()

    real_replace = os.replace
    failed = False

    def fail_after_new_locale(source_path, target_path):
        nonlocal failed
        source_path = Path(source_path)
        target_path = Path(target_path)
        if (
            not failed
            and ".restore." in source_path.name
            and target_path.name == "es_EC.json"
        ):
            failed = True
            raise OSError("simulated failure after creating en_US")
        return real_replace(source_path, target_path)

    monkeypatch.setattr(os, "replace", fail_after_new_locale)
    with pytest.raises(PersonalDictionaryBackupError):
        PersonalDictionaryBackupManager(target).restore(backup, mode="replace")

    assert not target.for_locale("en_US").path.exists()
    assert target.for_locale("es_EC").path.read_bytes() == original_spanish


def test_backup_manager_translates_store_lock_timeout(tmp_path: Path):
    root = tmp_path / "personal"
    root.mkdir()
    lock = root / ".personal-dictionaries.lock"
    lock.write_text("live", encoding="ascii")
    manager = PersonalDictionaryBackupManager(
        PersonalDictionaryStore(root),
        lock_timeout=0.01,
        stale_lock_seconds=30,
    )

    with pytest.raises(PersonalDictionaryBackupError) as captured:
        manager.export(tmp_path / "backup.ptlbackup")

    assert captured.value.operation == "export"
    assert captured.value.path == tmp_path / "backup.ptlbackup"
    lock.unlink()


def test_restore_never_touches_official_dictionary_files(tmp_path: Path):
    official = tmp_path / "official"
    official.mkdir()
    aff = official / "es_EC.aff"
    dic = official / "es_EC.dic"
    aff.write_bytes(b"SET UTF-8\n")
    dic.write_bytes(b"1\nhola\n")
    originals = (aff.read_bytes(), dic.read_bytes())

    source = PersonalDictionaryStore(tmp_path / "source")
    source.for_locale("es_EC").add_word("requinto")
    backup = tmp_path / "backup.ptlbackup"
    PersonalDictionaryBackupManager(source).export(backup)
    PersonalDictionaryBackupManager(
        PersonalDictionaryStore(tmp_path / "target")
    ).restore(backup)

    assert (aff.read_bytes(), dic.read_bytes()) == originals
