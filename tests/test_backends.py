from __future__ import annotations

from pathlib import Path

import pytest

from pyqt6_linguistic_tools import (
    BackendCache,
    BackendCapabilities,
    BackendMetadata,
    DictionaryMetadata,
    DictionaryNotFoundError,
    PyThesBackend,
    SpellCheckerBackend,
    SpyllsBackend,
    ThesaurusBackend,
    UnsupportedOperationError,
)
from pyqt6_linguistic_tools.backends.base import LinguisticBackend


@pytest.fixture
def spelling_root(tmp_path: Path) -> Path:
    root = tmp_path / "en_TEST"
    root.with_suffix(".aff").write_text(
        "SET UTF-8\nTRY abcdefghijklmnopqrstuvwxyz\n",
        encoding="utf-8",
    )
    root.with_suffix(".dic").write_text(
        "3\nhello\nworld\nspelling\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def thesaurus_data(tmp_path: Path) -> Path:
    path = tmp_path / "th_en_TEST_v2.dat"
    path.write_text(
        "UTF-8\n"
        "bright|2\n"
        "adj|shining|radiant|luminous\n"
        "quality|intelligent|clever|radiant\n",
        encoding="utf-8",
    )
    return path


def test_spylls_backend_loads_lazily_and_hides_engine_values(spelling_root: Path):
    backend: SpellCheckerBackend = SpyllsBackend(spelling_root, locale="en_TEST")

    assert not backend.loaded
    assert backend.metadata.dictionary.locale == "en_TEST"
    assert backend.check_word("hello")
    assert not backend.check_word("hellp")
    assert backend.loaded
    assert backend.metadata.name == "spylls"
    assert backend.metadata.dictionary.encoding == "UTF-8"
    assert backend.suggest("hellp", limit=1) == ("hello",)
    assert backend.suggest("hellp", limit=0) == ()

    with pytest.raises(UnsupportedOperationError):
        backend.add_word("toolkit")

    backend.unload()
    assert not backend.loaded


def test_spylls_backend_reports_missing_pair_without_engine_error(tmp_path: Path):
    root = tmp_path / "missing"
    root.with_suffix(".aff").write_text("SET UTF-8\n", encoding="utf-8")

    with pytest.raises(DictionaryNotFoundError) as captured:
        SpyllsBackend(root).check_word("word")

    assert captured.value.backend == "spylls"
    assert captured.value.operation == "load_dictionary"
    assert captured.value.path == root.with_suffix(".dic")


def test_pythes_backend_loads_lazily_and_returns_stable_models(
    thesaurus_data: Path,
):
    backend: ThesaurusBackend = PyThesBackend(
        thesaurus_data,
        locale="en_TEST",
        lookup_cache_size=2,
    )

    assert not backend.loaded
    entry = backend.lookup("BRIGHT")

    assert backend.loaded
    assert backend.metadata.dictionary.encoding == "UTF-8"
    assert entry is not None
    assert entry.word == "bright"
    assert entry.meanings[0].part_of_speech == "adj"
    assert entry.meanings[0].meaning == "shining"
    assert entry.meanings[0].synonyms == ("radiant", "luminous")
    assert backend.synonyms("bright") == (
        "shining",
        "radiant",
        "luminous",
        "intelligent",
        "clever",
    )
    assert backend.lookup("absent") is None

    backend.unload()
    assert not backend.loaded


class RecordingBackend(LinguisticBackend):
    def __init__(self, name: str) -> None:
        self.name = name
        self.unload_count = 0

    @classmethod
    def available(cls) -> bool:
        return True

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name=self.name,
            version="test",
            capabilities=BackendCapabilities(),
            dictionary=DictionaryMetadata(
                locale=self.name,
                paths=(),
                loaded=self.loaded,
            ),
        )

    @property
    def loaded(self) -> bool:
        return False

    def load_dictionary(self) -> None:
        pass

    def unload(self) -> None:
        self.unload_count += 1


def test_backend_cache_is_lru_bounded_and_unloads_evictions():
    cache: BackendCache[str, RecordingBackend] = BackendCache(max_size=2)
    first = cache.get_or_create("first", lambda: RecordingBackend("first"))
    second = cache.get_or_create("second", lambda: RecordingBackend("second"))

    assert cache.get_or_create("first", lambda: RecordingBackend("unused")) is first
    third = cache.get_or_create("third", lambda: RecordingBackend("third"))

    assert cache.keys() == ("first", "third")
    assert second.unload_count == 1
    assert first.unload_count == 0

    cache.clear()
    assert len(cache) == 0
    assert first.unload_count == 1
    assert third.unload_count == 1


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_backend_cache_rejects_invalid_limits(value):
    with pytest.raises((TypeError, ValueError)):
        BackendCache(max_size=value)
