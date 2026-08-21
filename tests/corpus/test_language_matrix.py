from __future__ import annotations

import gc

import pytest

from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    SpyllsBackend,
)


LANGUAGE_MATRIX = (
    (
        "English",
        "en_US",
        "dict-en/en_US",
        ("house", "music", "beautiful", "world"),
    ),
    (
        "Spanish",
        "es_EC",
        "dict-es/es_EC",
        ("Canta", "Toda", "maravillas", "creación", "Señor"),
    ),
    (
        "French",
        "fr",
        "dict-fr/fr",
        ("français", "création", "école", "France"),
    ),
    (
        "German",
        "de_DE",
        "dict-de/de_DE_frami",
        ("Haus", "Straße", "schön", "Deutschland"),
    ),
    (
        "Italian",
        "it_IT",
        "dict-it/it_IT",
        ("casa", "musica", "bello", "Italia"),
    ),
    (
        "Portuguese (Brazil)",
        "pt_BR",
        "dict-pt-BR/pt_BR",
        ("casa", "música", "Brasil", "bonito"),
    ),
    (
        "Portuguese (Portugal)",
        "pt_PT",
        "dict-pt-PT/pt_PT",
        ("casa", "música", "Portugal", "bonito"),
    ),
    (
        "Dutch",
        "nl_NL",
        "dict-nl/nl_NL",
        ("huis", "mooi", "Nederland", "muziek"),
    ),
    (
        "Polish",
        "pl_PL",
        "dict-pl/pl_PL",
        ("dom", "Polska", "piękny", "muzyka"),
    ),
    (
        "Russian",
        "ru_RU",
        "dict-ru/ru_RU",
        ("Москва", "привет", "Россия", "музыка"),
    ),
    (
        "Ukrainian",
        "uk_UA",
        "dict-uk/uk_UA",
        ("Україна", "Київ", "привіт", "музика"),
    ),
    (
        "Greek",
        "el_GR",
        "dict-el/el_GR",
        ("Ελλάδα", "σπίτι", "κόσμος", "μουσική"),
    ),
    (
        "Turkish",
        "tr_TR",
        "dict-tr/tr_TR",
        ("Türkiye", "ev", "güzel", "müzik"),
    ),
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
@pytest.mark.parametrize(
    ("language_name", "locale", "relative_root", "accepted_words"),
    LANGUAGE_MATRIX,
    ids=tuple(case[0] for case in LANGUAGE_MATRIX),
)
def test_pinned_language_acceptance_matrix(
    dictionary_corpus,
    language_name,
    locale,
    relative_root,
    accepted_words,
):
    """Verify curated words and one clearly invented error per real locale."""
    backend = SpyllsBackend(
        dictionary_corpus / relative_root,
        locale=locale,
    )

    rejected_word = f"zzqxx{accepted_words[0]}"
    rejected = backend.check_word(rejected_word)
    accepted = {word: backend.check_word(word) for word in accepted_words}

    assert all(accepted.values()), f"{language_name}: rejected {accepted}"
    assert not rejected, f"{language_name}: accepted invented word {rejected_word}"
    assert backend.metadata.dictionary.locale == locale
    assert backend.metadata.dictionary.encoding

    backend.unload()
    del backend
    gc.collect()


@pytest.mark.corpus
def test_collection_contains_languages_beyond_the_curated_matrix(
    libreoffice_registry,
):
    curated = {
        locale.split("_", 1)[0]
        for _name, locale, _root, _words in LANGUAGE_MATRIX
    }
    discovered = {
        entry.locale.split("_", 1)[0]
        for entry in libreoffice_registry.spelling_dictionaries()
    }

    assert curated <= discovered
    assert {"af", "ar", "bg", "he", "hi", "ko", "th", "vi"} <= discovered
    assert len(discovered - curated) >= 20
