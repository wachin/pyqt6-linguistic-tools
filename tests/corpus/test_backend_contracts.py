import pytest

from pyqt6_linguistic_tools import PyThesBackend, SpyllsBackend


@pytest.mark.corpus
def test_spylls_backend_contract_with_real_ecuador_dictionary(dictionary_corpus):
    backend = SpyllsBackend(
        dictionary_corpus / "dict-es" / "es_EC",
        locale="es_EC",
    )

    assert backend.check_word("Ecuador")
    assert backend.check_word("ecuatoriano")
    assert backend.check_word("canción")
    assert backend.check_word("niño")
    assert not backend.check_word("Ecuaddor")
    assert "Ecuador" in backend.suggest("Ecuaddor", limit=8)
    assert backend.metadata.dictionary.encoding == "UTF-8"

    backend.unload()
    assert not backend.loaded


@pytest.mark.corpus
def test_pythes_backend_contract_with_real_spanish_thesaurus(dictionary_corpus):
    backend = PyThesBackend(
        dictionary_corpus / "dict-es" / "th_es_v2.dat",
        locale="es",
        lookup_cache_size=32,
    )

    entry = backend.lookup("feliz")
    assert entry is not None
    assert entry.word == "feliz"
    assert len(entry.meanings) > 1
    assert "dichoso" in backend.synonyms("feliz")
    assert backend.metadata.dictionary.encoding == "ISO8859-1"

    backend.unload()
    assert not backend.loaded
