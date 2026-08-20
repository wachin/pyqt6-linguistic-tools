import pytest

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
)


@pytest.fixture(scope="module")
def libreoffice_registry(dictionary_corpus):
    return DictionaryRegistry(
        (
            DirectoryDictionaryProvider(
                dictionary_corpus,
                source="libreoffice-corpus",
                priority=DictionarySourcePriority.MANAGED,
            ),
        )
    )


@pytest.mark.corpus
def test_registry_discovers_complete_libreoffice_matrix(libreoffice_registry):
    entries = libreoffice_registry.discover()

    assert len(entries) == 90
    assert len({entry.locale for entry in entries}) == len(entries)
    assert len(libreoffice_registry.spelling_dictionaries()) == 89
    assert all(entry.aff_path.is_file() for entry in entries if entry.aff_path)
    assert all(entry.dic_path.is_file() for entry in entries if entry.dic_path)
    assert all(
        not entry.dic_path.name.startswith("hyph_")
        for entry in entries
        if entry.dic_path
    )


@pytest.mark.corpus
def test_registry_pairs_ecuador_with_generic_spanish_thesaurus(
    libreoffice_registry,
):
    ecuador = libreoffice_registry.get("es_EC")

    assert ecuador is not None
    assert ecuador.display_name == "Español (Ecuador)"
    assert ecuador.aff_path.name == "es_EC.aff"
    assert ecuador.dic_path.name == "es_EC.dic"
    assert ecuador.thesaurus_dat.name == "th_es_v2.dat"
    assert ecuador.thesaurus_idx.name == "th_es_v2.idx"
    assert ecuador.spelling_locale == "es_EC"
    assert ecuador.thesaurus_locale == "es"
    assert ecuador.uses_language_fallback


@pytest.mark.corpus
def test_registry_recognizes_all_spanish_regional_variants(libreoffice_registry):
    expected = {
        "es_AR", "es_BO", "es_CL", "es_CO", "es_CR", "es_CU", "es_DO",
        "es_EC", "es_ES", "es_GQ", "es_GT", "es_HN", "es_MX", "es_NI",
        "es_PA", "es_PE", "es_PH", "es_PR", "es_PY", "es_SV", "es_US",
        "es_UY", "es_VE",
    }
    regional = {
        entry.locale
        for entry in libreoffice_registry.discover()
        if entry.locale.startswith("es_")
    }

    assert regional == expected
    assert all(libreoffice_registry.get(locale).has_thesaurus for locale in expected)


@pytest.mark.corpus
def test_registry_parses_nonstandard_thesaurus_suffixes(libreoffice_registry):
    assert libreoffice_registry.get("ca_ES").thesaurus_dat.name == "th_ca_ES_v3.dat"
    assert (
        libreoffice_registry.get("ru_RU").thesaurus_dat.name
        == "th_ru_RU_M_aot_and_v2.dat"
    )

