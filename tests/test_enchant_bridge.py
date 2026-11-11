from __future__ import annotations

from pathlib import Path

from pyqt6_linguistic_tools import (
    PersonalDictionaryStore,
    enchant_config_dir,
    export_enchant_personal,
    import_enchant_personal,
)


def test_enchant_import_export_round_trip(tmp_path: Path):
    personal = PersonalDictionaryStore(tmp_path / "personal")
    enchant = tmp_path / "enchant"
    enchant.mkdir()
    source = enchant / "es_EC.dic"
    source.write_text(
        "# Enchant personal words\nXipixapa\nmoyuyo\n\nChocotete\n",
        encoding="utf-8",
    )

    imported = import_enchant_personal(personal, config_dir=enchant)
    assert imported == {"es_EC": 3}
    assert personal.for_locale("es_EC").words() == (
        "Chocotete",
        "moyuyo",
        "Xipixapa",
    )

    personal.for_locale("es_EC").add_word("nueva")
    exported = export_enchant_personal(personal, config_dir=enchant)
    assert exported == {"es_EC": 1}
    text = source.read_text(encoding="utf-8")
    assert "# Enchant personal words" in text
    assert "nueva" in text
    assert text.count("Xipixapa") == 1


def test_enchant_export_can_replace_words_but_keep_comments(tmp_path: Path):
    personal = PersonalDictionaryStore(tmp_path / "personal")
    personal.for_locale("es_EC").add_word("nueva")
    enchant = tmp_path / "enchant"
    enchant.mkdir()
    target = enchant / "es_EC.dic"
    target.write_text("# keep me\nvieja\n", encoding="utf-8")

    export_enchant_personal(personal, config_dir=enchant, merge=False)
    text = target.read_text(encoding="utf-8")

    assert "# keep me" in text
    assert "nueva" in text
    assert "vieja" not in text


def test_enchant_config_dir_honors_the_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ENCHANT_CONFIG_DIR", str(tmp_path / "enchant"))
    assert enchant_config_dir() == tmp_path / "enchant"
