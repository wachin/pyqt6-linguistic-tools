"""Deterministic tests for dictionary compatibility report generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pyqt6_linguistic_tools import (
    CompatibilityClassification,
    CompatibilityComponentResult,
    CompatibilityLocaleResult,
    CompatibilityReportMetadata,
    DictionaryCompatibilityReport,
    ValidationCheck,
    ValidationStatus,
    generate_compatibility_report,
    serialize_report,
    write_report,
)
from pyqt6_linguistic_tools.models import DictionaryValidationReport
from pyqt6_linguistic_tools.validation import DictionaryValidator


class TestCompatibilityReportModels:
    def test_compatibility_classification_values(self):
        assert CompatibilityClassification.READY.value == "ready"
        assert CompatibilityClassification.LIMITED.value == "limited"
        assert CompatibilityClassification.UNSUPPORTED.value == "unsupported"

    def test_compatibility_component_result_status_pass(self):
        checks = (
            ValidationCheck("test", ValidationStatus.PASS, "ok"),
            ValidationCheck("test2", ValidationStatus.PASS, "ok"),
        )
        result = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=checks,
            classification=CompatibilityClassification.READY,
        )
        assert result.status is ValidationStatus.PASS

    def test_compatibility_component_result_status_fail(self):
        checks = (
            ValidationCheck("test", ValidationStatus.PASS, "ok"),
            ValidationCheck("test2", ValidationStatus.FAIL, "fail"),
        )
        result = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=checks,
            classification=CompatibilityClassification.UNSUPPORTED,
        )
        assert result.status is ValidationStatus.FAIL

    def test_compatibility_component_result_status_warning(self):
        checks = (
            ValidationCheck("test", ValidationStatus.PASS, "ok"),
            ValidationCheck("test2", ValidationStatus.WARNING, "warn"),
        )
        result = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=checks,
            classification=CompatibilityClassification.LIMITED,
        )
        assert result.status is ValidationStatus.WARNING

    def test_compatibility_locale_result_overall_ready(self):
        spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="en_US",
            source_path="dict-en/th_en_US_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=spelling,
            thesaurus=thesaurus,
        )
        assert locale.overall_classification is CompatibilityClassification.READY

    def test_compatibility_locale_result_overall_limited(self):
        spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="en_US",
            source_path="dict-en/th_en_US_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.WARNING, "warn"),),
            classification=CompatibilityClassification.LIMITED,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=spelling,
            thesaurus=thesaurus,
        )
        assert locale.overall_classification is CompatibilityClassification.LIMITED

    def test_compatibility_locale_result_overall_unsupported(self):
        spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.FAIL, "fail"),),
            classification=CompatibilityClassification.UNSUPPORTED,
        )
        thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="en_US",
            source_path="dict-en/th_en_US_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=spelling,
            thesaurus=thesaurus,
        )
        assert locale.overall_classification is CompatibilityClassification.UNSUPPORTED

    def test_compatibility_locale_result_spelling_only_ready(self):
        spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=spelling,
            thesaurus=None,
        )
        assert locale.overall_classification is CompatibilityClassification.READY

    def test_compatibility_locale_result_thesaurus_only_ready(self):
        thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="en_US",
            source_path="dict-en/th_en_US_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=None,
            thesaurus=thesaurus,
        )
        assert locale.overall_classification is CompatibilityClassification.READY

    def test_compatibility_locale_result_no_components(self):
        locale = CompatibilityLocaleResult(
            locale="xx_XX",
            display_name="Unknown",
            spelling=None,
            thesaurus=None,
        )
        assert locale.overall_classification is CompatibilityClassification.UNSUPPORTED


class TestSerializeReport:
    def test_serialize_report_deterministic_order(self):
        metadata = CompatibilityReportMetadata(
            schema_version=1,
            generated_at_utc="2026-08-21T12:00:00+00:00",
            toolkit_version="0.1.0.dev0",
            spylls_version="1.0.0",
            pythes_version="1.0.0",
            python_version="3.10.12",
            platform="Linux-6.8.0",
            machine="x86_64",
            corpus_identity="dicts",
        )
        spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="en_US",
            source_path="dict-en/th_en_US_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        locale = CompatibilityLocaleResult(
            locale="en_US",
            display_name="English (US)",
            spelling=spelling,
            thesaurus=thesaurus,
        )
        report = DictionaryCompatibilityReport(
            metadata=metadata,
            locales=(locale,),
        )

        serialized1 = serialize_report(report)
        serialized2 = serialize_report(report)
        assert serialized1 == serialized2

        parsed = json.loads(serialized1)
        assert parsed["metadata"]["schema_version"] == 1
        assert parsed["locales"][0]["locale"] == "en_US"
        assert parsed["locales"][0]["overall_classification"] == "ready"

    def test_serialize_report_sorted_keys(self):
        metadata = CompatibilityReportMetadata(
            schema_version=1,
            generated_at_utc="2026-08-21T12:00:00+00:00",
            toolkit_version="0.1.0.dev0",
            spylls_version="1.0.0",
            pythes_version="1.0.0",
            python_version="3.10.12",
            platform="Linux-6.8.0",
            machine="x86_64",
        )
        report = DictionaryCompatibilityReport(metadata=metadata, locales=())
        serialized = serialize_report(report)
        parsed = json.loads(serialized)

        keys = list(parsed.keys())
        assert keys == sorted(keys)

        if "locales" in parsed and parsed["locales"]:
            locale_keys = list(parsed["locales"][0].keys())
            assert locale_keys == sorted(locale_keys)

    def test_write_report_creates_parent_directories(self, tmp_path):
        metadata = CompatibilityReportMetadata(
            schema_version=1,
            generated_at_utc="2026-08-21T12:00:00+00:00",
            toolkit_version="0.1.0.dev0",
            spylls_version="1.0.0",
            pythes_version="1.0.0",
            python_version="3.10.12",
            platform="Linux-6.8.0",
            machine="x86_64",
        )
        report = DictionaryCompatibilityReport(metadata=metadata, locales=())
        output = tmp_path / "subdir" / "report.json"
        write_report(report, output)
        assert output.is_file()
        content = output.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert "schema_version" in content


class TestGenerateCompatibilityReport:
    def test_generate_report_empty_corpus(self, tmp_path):
        corpus = tmp_path / "empty"
        corpus.mkdir()
        report = generate_compatibility_report(corpus)
        assert isinstance(report, DictionaryCompatibilityReport)
        assert report.metadata.schema_version == 1
        assert report.locales == ()

    def test_generate_report_missing_corpus(self, tmp_path):
        corpus = tmp_path / "missing"
        with pytest.raises(NotADirectoryError):
            generate_compatibility_report(corpus)

    def test_generate_report_structure(self, tmp_path):
        corpus = tmp_path / "dicts"
        corpus.mkdir()

        dict_dir = corpus / "dict-en"
        dict_dir.mkdir()

        aff_content = "SET UTF-8\n"
        dic_content = "1\nexample\n"
        (dict_dir / "en_US.aff").write_text(aff_content)
        (dict_dir / "en_US.dic").write_text(dic_content)

        report = generate_compatibility_report(corpus, sample_size=2)
        assert len(report.locales) == 1
        locale = report.locales[0]
        assert locale.locale == "en_US"
        assert locale.spelling is not None
        assert locale.spelling.component == "spelling"
        assert locale.spelling.source_encoding == "utf-8"
        assert locale.thesaurus is None

    def test_generate_report_with_thesaurus(self, tmp_path):
        corpus = tmp_path / "dicts"
        corpus.mkdir()

        dict_dir = corpus / "dict-en"
        dict_dir.mkdir()

        aff_content = "SET UTF-8\n"
        dic_content = "1\nexample\n"
        (dict_dir / "en_US.aff").write_text(aff_content)
        (dict_dir / "en_US.dic").write_text(dic_content)

        dat_content = "UTF-8\n1\nexample|0\n1|meaning|synonym\n"
        idx_content = "UTF-8\n1\nexample|0\n"
        (dict_dir / "th_en_US_v2.dat").write_text(dat_content)
        (dict_dir / "th_en_US_v2.idx").write_text(idx_content)

        report = generate_compatibility_report(corpus, sample_size=2)
        assert len(report.locales) == 1
        locale = report.locales[0]
        assert locale.locale == "en_US"
        assert locale.spelling is not None
        assert locale.thesaurus is not None
        assert locale.thesaurus.component == "thesaurus"

    def test_generate_report_locale_ordering(self, tmp_path):
        corpus = tmp_path / "dicts"
        corpus.mkdir()

        for locale_code in ["de_DE", "en_US", "es_EC", "fr_FR"]:
            dict_dir = corpus / f"dict-{locale_code.split('_')[0]}"
            dict_dir.mkdir(exist_ok=True)
            (dict_dir / f"{locale_code}.aff").write_text("SET UTF-8\n")
            (dict_dir / f"{locale_code}.dic").write_text("1\nexample\n")

        report = generate_compatibility_report(corpus, sample_size=1)
        locales = [l.locale for l in report.locales]
        assert locales == ["de_DE", "en_US", "es_EC", "fr_FR"]

    def test_generate_report_spelling_classification_fail(self, tmp_path):
        corpus = tmp_path / "dicts"
        corpus.mkdir()

        dict_dir = corpus / "dict-xx"
        dict_dir.mkdir()
        (dict_dir / "xx_XX.aff").write_text("SET UTF-8\n")
        (dict_dir / "xx_XX.dic").write_text("1\nword\n")

        with patch.object(DictionaryValidator, "validate_spelling") as mock_validate:
            mock_validate.return_value = DictionaryValidationReport(
                component="spelling",
                locale="xx_XX",
                checks=(
                    ValidationCheck(
                        "engine_load",
                        ValidationStatus.FAIL,
                        "load failed",
                    ),
                ),
                encoding="utf-8",
            )
            report = generate_compatibility_report(corpus, sample_size=1)
            assert report.locales[0].spelling.classification is CompatibilityClassification.UNSUPPORTED

    def test_generate_report_spelling_classification_warning(self, tmp_path):
        corpus = tmp_path / "dicts"
        corpus.mkdir()

        dict_dir = corpus / "dict-xx"
        dict_dir.mkdir()
        (dict_dir / "xx_XX.aff").write_text("SET UTF-8\n")
        (dict_dir / "xx_XX.dic").write_text("1\nword\n")

        with patch.object(DictionaryValidator, "validate_spelling") as mock_validate:
            mock_validate.return_value = DictionaryValidationReport(
                component="spelling",
                locale="xx_XX",
                checks=(
                    ValidationCheck(
                        "entry_count",
                        ValidationStatus.WARNING,
                        "count mismatch",
                    ),
                ),
                encoding="utf-8",
            )
            report = generate_compatibility_report(corpus, sample_size=1)
            assert report.locales[0].spelling.classification is CompatibilityClassification.LIMITED


class TestCompatibilityReportSummary:
    def test_summary_counts(self):
        metadata = CompatibilityReportMetadata(
            schema_version=1,
            generated_at_utc="2026-08-21T12:00:00+00:00",
            toolkit_version="0.1.0.dev0",
            spylls_version="1.0.0",
            pythes_version="1.0.0",
            python_version="3.10.12",
            platform="Linux-6.8.0",
            machine="x86_64",
        )
        ready_spelling = CompatibilityComponentResult(
            component="spelling",
            locale="en_US",
            source_path="dict-en/en_US.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.PASS, "ok"),),
            classification=CompatibilityClassification.READY,
        )
        limited_spelling = CompatibilityComponentResult(
            component="spelling",
            locale="fr_FR",
            source_path="dict-fr/fr_FR.dic",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.WARNING, "warn"),),
            classification=CompatibilityClassification.LIMITED,
        )
        unsupported_thesaurus = CompatibilityComponentResult(
            component="thesaurus",
            locale="de_DE",
            source_path="dict-de/th_de_DE_v2.dat",
            source_encoding="utf-8",
            checks=(ValidationCheck("t", ValidationStatus.FAIL, "fail"),),
            classification=CompatibilityClassification.UNSUPPORTED,
        )
        locales = (
            CompatibilityLocaleResult(
                locale="en_US",
                display_name="English (US)",
                spelling=ready_spelling,
                thesaurus=None,
            ),
            CompatibilityLocaleResult(
                locale="fr_FR",
                display_name="French (France)",
                spelling=limited_spelling,
                thesaurus=None,
            ),
            CompatibilityLocaleResult(
                locale="de_DE",
                display_name="German (Germany)",
                spelling=None,
                thesaurus=unsupported_thesaurus,
            ),
        )
        report = DictionaryCompatibilityReport(metadata=metadata, locales=locales)
        summary = report.summary
        assert summary["ready"] == 1
        assert summary["limited"] == 1
        assert summary["unsupported"] == 1