from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    DictionaryImportError,
    DictionaryValidator,
    UserDictionaryProvider,
    ValidationStatus,
    regenerate_thesaurus_index,
)


def _write(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.write_text(text, encoding=encoding)
    return path


def _spelling(tmp_path: Path) -> tuple[Path, Path]:
    return (
        _write(tmp_path / "es_EC.aff", "SET UTF-8\nTRY abcdefghijklmnñopqrstuvwxyz\n"),
        _write(tmp_path / "es_EC.dic", "3\nEcuador\nniño\ncanción\n"),
    )


def _thesaurus(tmp_path: Path, *, index_offset: int = 6) -> tuple[Path, Path]:
    dat = _write(
        tmp_path / "th_en_TEST_v2.dat",
        "UTF-8\nbright|1\nadj|shining|radiant\n",
    )
    idx = _write(
        tmp_path / "th_en_TEST_v2.idx",
        f"UTF-8\n1\nbright|{index_offset}\n",
    )
    return dat, idx


def test_spelling_validator_reports_encoding_load_count_and_words(tmp_path: Path):
    aff, dic = _spelling(tmp_path)

    report = DictionaryValidator(sample_size=2).validate_spelling(
        aff,
        dic,
        locale="es_EC",
        representative_words=("Ecuador", "niño", "canción"),
    )

    assert report.status is ValidationStatus.PASS
    assert report.encoding == "utf-8"
    assert report.sampled_entries == ("Ecuador", "niño", "canción")
    assert {check.code for check in report.checks} >= {
        "aff_exists",
        "dic_exists",
        "encoding_declaration",
        "dictionary_decoding",
        "entry_count",
        "engine_load",
        "representative_words",
    }


def test_spelling_validator_fails_unknown_encoding_before_engine_load(tmp_path: Path):
    aff = _write(tmp_path / "bad.aff", "SET NOT-A-CODEC\n")
    dic = _write(tmp_path / "bad.dic", "1\nword\n")

    report = DictionaryValidator().validate_spelling(aff, dic)

    assert report.status is ValidationStatus.FAIL
    assert not report.usable
    assert report.checks[-1].code == "encoding_declaration"


def test_spelling_validator_detects_malformed_affix_rules(tmp_path: Path):
    aff = _write(tmp_path / "bad.aff", "SET UTF-8\nFLAG broken\n")
    dic = _write(tmp_path / "bad.dic", "1\nword/A\n")

    report = DictionaryValidator().validate_spelling(aff, dic)

    assert report.status is ValidationStatus.FAIL
    assert next(check for check in report.checks if check.code == "engine_load").status is ValidationStatus.FAIL


def test_explicit_representative_word_failure_is_not_hidden(tmp_path: Path):
    aff, dic = _spelling(tmp_path)

    report = DictionaryValidator().validate_spelling(
        aff,
        dic,
        representative_words=("definitely-absent",),
    )

    assert report.status is ValidationStatus.FAIL
    assert report.sampled_entries == ()


def test_thesaurus_validator_checks_count_offsets_and_lookup(tmp_path: Path):
    dat, idx = _thesaurus(tmp_path)

    report = DictionaryValidator(sample_size=3).validate_thesaurus(
        dat,
        idx,
        locale="en_TEST",
        representative_words=("bright",),
    )

    assert report.status is ValidationStatus.PASS
    assert report.encoding == "utf-8"
    assert report.sampled_entries == ("bright",)
    assert next(check for check in report.checks if check.code == "sampled_offsets").status is ValidationStatus.PASS


def test_recoverable_stale_thesaurus_index_is_a_warning(tmp_path: Path):
    dat, idx = _thesaurus(tmp_path, index_offset=0)

    report = DictionaryValidator().validate_thesaurus(dat, idx)

    assert report.status is ValidationStatus.WARNING
    assert report.usable
    assert next(check for check in report.checks if check.code == "sampled_offsets").status is ValidationStatus.WARNING
    assert next(check for check in report.checks if check.code == "engine_load").status is ValidationStatus.WARNING


def test_missing_thesaurus_index_is_a_usable_warning(tmp_path: Path):
    dat, idx = _thesaurus(tmp_path)
    idx.unlink()

    report = DictionaryValidator().validate_thesaurus(dat)

    assert report.status is ValidationStatus.WARNING
    assert report.usable
    assert report.sampled_entries == ("bright",)


def test_regenerate_thesaurus_index_is_explicit_and_validated(tmp_path: Path):
    dat, idx = _thesaurus(tmp_path)
    idx.unlink()

    generated = regenerate_thesaurus_index(dat)

    assert generated == idx
    assert generated.is_file()
    assert DictionaryValidator().validate_thesaurus(dat, generated).usable


def test_manual_import_removes_staging_when_deep_validation_fails(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    aff = _write(source / "broken.aff", "SET NOT-A-CODEC\n")
    dic = _write(source / "broken.dic", "1\nword\n")
    provider = UserDictionaryProvider(tmp_path / "user")

    with pytest.raises(DictionaryImportError) as captured:
        provider.import_files([aff, dic], bundle_name="broken")

    assert captured.value.validation is not None
    assert captured.value.validation.status is ValidationStatus.FAIL
    assert not (provider.root / "broken").exists()
    assert not any(provider.root.iterdir())


def test_validated_import_returns_recoverable_warnings(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    dat, idx = _thesaurus(source, index_offset=0)
    provider = UserDictionaryProvider(tmp_path / "user")

    result = provider.import_validated_files([dat, idx], bundle_name="warning")

    assert result.destination == provider.root / "warning"
    assert result.validation.status is ValidationStatus.WARNING
    assert result.validation.usable
