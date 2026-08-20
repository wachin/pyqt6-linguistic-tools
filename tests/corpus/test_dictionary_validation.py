import pytest

from pyqt6_linguistic_tools import DictionaryValidator, ValidationStatus


@pytest.mark.corpus
def test_real_ecuador_spelling_validation(dictionary_corpus):
    root = dictionary_corpus / "dict-es" / "es_EC"
    report = DictionaryValidator(sample_size=8).validate_spelling(
        root.with_suffix(".aff"),
        root.with_suffix(".dic"),
        locale="es_EC",
        representative_words=("Ecuador", "ecuatoriano", "canción", "niño"),
    )

    assert report.status is ValidationStatus.PASS
    assert report.encoding == "utf-8"


@pytest.mark.corpus
def test_real_legacy_spanish_thesaurus_validation(dictionary_corpus):
    dat = dictionary_corpus / "dict-es" / "th_es_v2.dat"
    report = DictionaryValidator(sample_size=8).validate_thesaurus(
        dat,
        dat.with_suffix(".idx"),
        locale="es",
        representative_words=("feliz", "casa", "música"),
    )

    assert report.status is ValidationStatus.PASS
    assert report.encoding == "iso8859-1"

