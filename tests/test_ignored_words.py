from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from pyqt6_linguistic_tools import IgnoredWords, IgnoredWordsStore


def test_ignore_once_is_stable_and_limited_to_one_occurrence():
    ignored = IgnoredWords("es-ec")

    assert ignored.ignore_once(
        "pentatónica", document_id="song-1", occurrence_id=(10, 21)
    )
    assert not ignored.ignore_once(
        "pentatónica", document_id="song-1", occurrence_id=(10, 21)
    )
    assert ignored.is_ignored(
        "pentatónica", document_id="song-1", occurrence_id=(10, 21)
    )
    # Rechecking the same occurrence does not consume the decision.
    assert ignored.is_ignored(
        "pentatónica", document_id="song-1", occurrence_id=(10, 21)
    )
    assert not ignored.is_ignored(
        "pentatónica", document_id="song-1", occurrence_id=(30, 41)
    )
    assert not ignored.is_ignored(
        "pentatónica", document_id="song-2", occurrence_id=(10, 21)
    )


def test_ignore_once_tracks_the_word_at_a_reused_occurrence():
    ignored = IgnoredWords("es_EC")
    ignored.ignore_once("primera", document_id="song", occurrence_id=1)

    assert ignored.ignore_once("segunda", document_id="song", occurrence_id=1)
    assert not ignored.is_ignored(
        "primera", document_id="song", occurrence_id=1
    )
    assert ignored.is_ignored("segunda", document_id="song", occurrence_id=1)


def test_document_ignore_does_not_leak_to_other_documents():
    ignored = IgnoredWords("es_EC")

    assert ignored.ignore_for_document("ChordFlow", document_id="flow")
    assert not ignored.ignore_for_document("ChordFlow", document_id="flow")
    assert ignored.is_ignored("ChordFlow", document_id="flow")
    assert not ignored.is_ignored("ChordFlow", document_id="pages")
    assert ignored.document_words("flow") == ("ChordFlow",)


def test_session_ignore_applies_to_every_document_for_one_locale():
    ignored = IgnoredWords("es_EC")

    assert ignored.ignore_for_session("requinto")
    assert ignored.is_ignored("requinto")
    assert ignored.is_ignored("requinto", document_id="flow")
    assert ignored.is_ignored("requinto", document_id="pages", occurrence_id=7)
    assert ignored.session_words() == ("requinto",)


def test_clear_operations_respect_scope_and_revision():
    ignored = IgnoredWords("es_EC")
    initial_revision = ignored.revision
    ignored.ignore_for_session("global")
    ignored.ignore_for_document("documento", document_id="song")
    ignored.ignore_once("aparición", document_id="song", occurrence_id=2)

    assert ignored.revision == initial_revision + 3
    assert ignored.clear_once(document_id="song", occurrence_id=2)
    assert not ignored.clear_once(document_id="song", occurrence_id=2)
    assert ignored.clear_document("song")
    assert not ignored.clear_document("song")
    assert ignored.is_ignored("global", document_id="song")
    assert ignored.clear_session()
    assert not ignored.clear_session()
    assert not ignored.clear_all()


def test_clear_document_removes_all_occurrence_decisions_but_not_session():
    ignored = IgnoredWords("es_EC")
    ignored.ignore_for_session("sesión")
    ignored.ignore_for_document("documento", document_id="song")
    ignored.ignore_once("uno", document_id="song", occurrence_id=1)
    ignored.ignore_once("dos", document_id="song", occurrence_id=2)

    assert ignored.clear_document("song")
    assert not ignored.is_ignored("documento", document_id="song")
    assert not ignored.is_ignored("uno", document_id="song", occurrence_id=1)
    assert not ignored.is_ignored("dos", document_id="song", occurrence_id=2)
    assert ignored.is_ignored("sesión", document_id="song")


def test_case_insensitive_mode_collapses_equivalent_words():
    ignored = IgnoredWords("es_EC", case_sensitive=False)

    assert ignored.ignore_for_session("ChordFlow")
    assert not ignored.ignore_for_session("chordflow")
    assert ignored.is_ignored("CHORDFLOW")
    assert ignored.session_words() == ("ChordFlow",)


def test_store_isolates_locales_and_returns_stable_collections():
    store = IgnoredWordsStore()
    spanish = store.for_locale("es-ec")
    english = store.for_locale("en_US")

    spanish.ignore_for_session("requinto")

    assert store.for_locale("es_EC") is spanish
    assert spanish.is_ignored("requinto")
    assert not english.is_ignored("requinto")
    assert store.active_locales() == ("en_US", "es_EC")
    assert store.clear_all()
    assert not store.clear_all()


@pytest.mark.parametrize("identifier", [None, [], {}])
def test_scope_identifiers_must_be_non_none_and_hashable(identifier):
    ignored = IgnoredWords("es_EC")

    with pytest.raises(TypeError):
        ignored.ignore_for_document("palabra", document_id=identifier)
    with pytest.raises(TypeError):
        ignored.ignore_once(
            "palabra", document_id="song", occurrence_id=identifier
        )


def test_occurrence_query_requires_a_document():
    ignored = IgnoredWords("es_EC")

    with pytest.raises(ValueError, match="requires document_id"):
        ignored.is_ignored("palabra", occurrence_id=1)


def test_invalid_words_are_rejected_without_changing_state():
    ignored = IgnoredWords("es_EC")

    with pytest.raises(ValueError):
        ignored.ignore_for_session("two words")
    assert ignored.revision == 0


def test_concurrent_session_updates_are_thread_safe():
    ignored = IgnoredWords("es_EC")
    words = tuple(f"palabra-{number}" for number in range(100))

    with ThreadPoolExecutor(max_workers=8) as executor:
        tuple(executor.map(ignored.ignore_for_session, words))

    assert ignored.session_words() == tuple(sorted(words))
    assert ignored.revision == len(words)
