"""Portable thesaurus backend implemented with the maintained PyThes fork."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from threading import RLock
from typing import Any

from pyqt6_linguistic_tools.backends.base import ThesaurusBackend
from pyqt6_linguistic_tools.errors import (
    BackendOperationError,
    BackendUnavailableError,
    DictionaryLoadError,
    DictionaryNotFoundError,
)
from pyqt6_linguistic_tools.models import (
    BackendCapabilities,
    BackendMetadata,
    DictionaryMetadata,
    ThesaurusEntry,
    ThesaurusMeaning,
)


def _data_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    return resolved.with_suffix(".dat") if resolved.suffix.lower() != ".dat" else resolved


class PyThesBackend(ThesaurusBackend):
    """Load one MyThes data set lazily and convert all engine values."""

    NAME = "pythes"
    VERSION = "1.0.0"
    CAPABILITIES = BackendCapabilities(thesaurus=True)

    def __init__(
        self,
        dictionary: str | Path,
        *,
        locale: str | None = None,
        lookup_cache_size: int = 256,
    ) -> None:
        if isinstance(lookup_cache_size, bool) or not isinstance(lookup_cache_size, int):
            raise TypeError("lookup_cache_size must be an integer")
        if lookup_cache_size < 0:
            raise ValueError("lookup_cache_size must be zero or greater")
        self._data_path = _data_path(dictionary)
        self._index_path = self._data_path.with_suffix(".idx")
        self._locale = locale or self._infer_locale(self._data_path.stem)
        self._lookup_cache_size = lookup_cache_size
        self._engine: Any | None = None
        self._encoding: str | None = None
        self._lock = RLock()

    @staticmethod
    def _infer_locale(stem: str) -> str:
        locale = stem[3:] if stem.startswith("th_") else stem
        return locale[:-3] if locale.endswith("_v2") else locale

    @classmethod
    def available(cls) -> bool:
        try:
            return find_spec("pythes") is not None
        except (ImportError, ValueError):
            return False

    @property
    def loaded(self) -> bool:
        return self._engine is not None

    @property
    def metadata(self) -> BackendMetadata:
        paths = (self._data_path,)
        if self._index_path.is_file():
            paths += (self._index_path,)
        return BackendMetadata(
            name=self.NAME,
            version=self.VERSION,
            capabilities=self.CAPABILITIES,
            dictionary=DictionaryMetadata(
                locale=self._locale,
                paths=paths,
                loaded=self.loaded,
                encoding=self._encoding,
            ),
        )

    def load_dictionary(self) -> None:
        with self._lock:
            if self._engine is not None:
                return
            if not self._data_path.is_file():
                raise DictionaryNotFoundError(
                    f"thesaurus data file not found: {self._data_path}",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=self._data_path,
                )
            if not self.available():
                raise BackendUnavailableError(
                    "PyThes is not available",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=self._data_path,
                )

            try:
                from pythes import PyThes

                engine = PyThes(self._data_path, cache_size=self._lookup_cache_size)
                encoding = engine.dat_encoding
            except Exception as error:
                raise DictionaryLoadError(
                    f"PyThes could not load thesaurus {self._data_path}",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=self._data_path,
                ) from error

            self._engine = engine
            self._encoding = str(encoding)

    def unload(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.clear_cache()
            self._engine = None
            self._encoding = None

    def lookup(self, word: str) -> ThesaurusEntry | None:
        if not isinstance(word, str):
            raise TypeError("word must be a string")
        with self._lock:
            self.load_dictionary()
            try:
                result = self._engine.lookup(word)
            except Exception as error:
                raise BackendOperationError(
                    "PyThes failed to look up a word",
                    backend=self.NAME,
                    operation="lookup",
                    path=self._data_path,
                ) from error

        if result is None:
            return None
        return ThesaurusEntry(
            word=str(result.word),
            meanings=tuple(
                ThesaurusMeaning(
                    part_of_speech=str(meaning.part_of_speech),
                    meaning=str(meaning.meaning),
                    synonyms=tuple(str(item) for item in meaning.synonyms),
                )
                for meaning in result.meanings
            ),
        )

