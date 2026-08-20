import pytest

from pyqt6_linguistic_tools import load_dictionary_catalog


@pytest.mark.corpus
def test_real_dictionary_catalog_is_valid(dictionary_corpus):
    catalog_path = dictionary_corpus.parent / "dictionaries.json"
    catalog = load_dictionary_catalog(catalog_path)

    assert len(catalog.dictionaries) == 57
    assert catalog.get("es").name == "Spanish"
    assert catalog.get("es").url.endswith("/dict-es.tar.gz")
    assert catalog.get("pt-BR").code == "pt_BR"
    assert not catalog.supports_verified_downloads
