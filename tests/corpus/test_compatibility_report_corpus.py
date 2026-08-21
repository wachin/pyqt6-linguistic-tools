"""Corpus integration tests for dictionary compatibility report."""

import pytest

from pyqt6_linguistic_tools import (
    CompatibilityClassification,
    generate_compatibility_report,
)


@pytest.mark.corpus
def test_compatibility_report_basic_structure(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    assert report.metadata.schema_version == 1
    assert report.metadata.toolkit_version != "unknown"
    assert report.metadata.spylls_version != "unknown"
    assert report.metadata.pythes_version != "unknown"
    assert report.metadata.python_version
    assert report.metadata.platform
    assert report.metadata.machine
    assert report.metadata.corpus_identity == "dicts"
    assert len(report.locales) > 0


@pytest.mark.corpus
def test_compatibility_report_locale_count_matches_registry(dictionary_corpus):
    from pyqt6_linguistic_tools import DictionaryRegistry, DirectoryDictionaryProvider, DictionarySourcePriority

    provider = DirectoryDictionaryProvider(
        dictionary_corpus,
        source="libreoffice-corpus",
        priority=DictionarySourcePriority.MANAGED,
    )
    registry = DictionaryRegistry((provider,))
    registry_entries = registry.discover()

    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    assert len(report.locales) == len(registry_entries)


@pytest.mark.corpus
def test_compatibility_report_ecuador_spelling_ready(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    ecuador = next((l for l in report.locales if l.locale == "es_EC"), None)
    assert ecuador is not None
    assert ecuador.spelling is not None
    assert ecuador.spelling.classification is CompatibilityClassification.READY
    assert ecuador.spelling.source_encoding == "utf-8"
    assert ecuador.spelling.source_path is not None


@pytest.mark.corpus
def test_compatibility_report_spanish_thesaurus_ready(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    spanish = next((l for l in report.locales if l.locale == "es"), None)
    assert spanish is not None
    assert spanish.thesaurus is not None
    assert spanish.thesaurus.classification is CompatibilityClassification.READY
    assert spanish.thesaurus.source_encoding == "iso8859-1"
    assert spanish.thesaurus.source_path is not None


@pytest.mark.corpus
def test_compatibility_report_spelling_only_locale(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    spelling_only = [l for l in report.locales if l.spelling is not None and l.thesaurus is None]
    assert len(spelling_only) > 0


@pytest.mark.corpus
def test_compatibility_report_thesaurus_only_locale(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    thesaurus_only = [l for l in report.locales if l.thesaurus is not None and l.spelling is None]
    assert len(thesaurus_only) > 0


@pytest.mark.corpus
def test_compatibility_report_both_components_locale(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    both = [l for l in report.locales if l.spelling is not None and l.thesaurus is not None]
    assert len(both) > 0


@pytest.mark.corpus
def test_compatibility_report_locale_ordering(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    locales = [l.locale for l in report.locales]
    assert locales == sorted(locales, key=lambda x: (x.split('_')[0], x))


@pytest.mark.corpus
def test_compatibility_report_summary_counts(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    summary = report.summary
    assert summary["ready"] >= 0
    assert summary["limited"] >= 0
    assert summary["unsupported"] >= 0
    assert sum(summary.values()) == len(report.locales)


@pytest.mark.corpus
def test_compatibility_report_checks_present(dictionary_corpus):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)

    for locale in report.locales:
        if locale.spelling is not None:
            check_codes = {c.code for c in locale.spelling.checks}
            assert "aff_exists" in check_codes
            assert "dic_exists" in check_codes
            assert "encoding_declaration" in check_codes
            assert "dictionary_decoding" in check_codes
            assert "entry_count" in check_codes
            assert "engine_load" in check_codes
            assert "representative_words" in check_codes

        if locale.thesaurus is not None:
            check_codes = {c.code for c in locale.thesaurus.checks}
            assert "dat_exists" in check_codes
            assert "idx_exists" in check_codes
            assert "encoding_declaration" in check_codes
            assert "index_count" in check_codes or "engine_load" in check_codes
            assert "representative_entries" in check_codes


@pytest.mark.corpus
def test_compatibility_report_deterministic_output(dictionary_corpus):
    report1 = generate_compatibility_report(dictionary_corpus, sample_size=2)
    report2 = generate_compatibility_report(dictionary_corpus, sample_size=2)

    from pyqt6_linguistic_tools import serialize_report
    assert serialize_report(report1) == serialize_report(report2)


@pytest.mark.corpus
def test_compatibility_report_serialization(dictionary_corpus, tmp_path):
    report = generate_compatibility_report(dictionary_corpus, sample_size=2)
    output = tmp_path / "compat-report.json"

    from pyqt6_linguistic_tools import write_report
    write_report(report, output)

    assert output.is_file()
    content = output.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert parsed["metadata"]["schema_version"] == 1
    assert len(parsed["locales"]) == len(report.locales)


import json