"""Portable spelling backend implemented with the maintained Spylls fork."""

from __future__ import annotations

from importlib.util import find_spec
from itertools import islice
from pathlib import Path
from threading import RLock
from typing import Any

from pyqt6_linguistic_tools.backends.base import SpellCheckerBackend
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
)


def _dictionary_root(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved.suffix.lower() in {".aff", ".dic"}:
        resolved = resolved.with_suffix("")
    return resolved


def _validate_word(word: str) -> None:
    if not isinstance(word, str):
        raise TypeError("word must be a string")


class SpyllsBackend(SpellCheckerBackend):
    """Load one Hunspell pair lazily and expose only toolkit values."""

    NAME = "spylls"
    VERSION = "0.1.7"
    CAPABILITIES = BackendCapabilities(spell_check=True, suggestions=True)

    def __init__(self, dictionary: str | Path, *, locale: str | None = None) -> None:
        self._root = _dictionary_root(dictionary)
        self._locale = locale or self._root.name
        self._engine: Any | None = None
        self._encoding: str | None = None
        self._version = self.VERSION
        self._lock = RLock()

    @classmethod
    def available(cls) -> bool:
        try:
            return find_spec("spylls.hunspell") is not None
        except (ImportError, ValueError):
            return False

    @property
    def loaded(self) -> bool:
        return self._engine is not None

    @property
    def metadata(self) -> BackendMetadata:
        return BackendMetadata(
            name=self.NAME,
            version=self._version,
            capabilities=self.CAPABILITIES,
            dictionary=DictionaryMetadata(
                locale=self._locale,
                paths=(self._root.with_suffix(".aff"), self._root.with_suffix(".dic")),
                loaded=self.loaded,
                encoding=self._encoding,
            ),
        )

    def load_dictionary(self) -> None:
        with self._lock:
            if self._engine is not None:
                return

            aff_path = self._root.with_suffix(".aff")
            dic_path = self._root.with_suffix(".dic")
            missing = next((path for path in (aff_path, dic_path) if not path.is_file()), None)
            if missing is not None:
                raise DictionaryNotFoundError(
                    f"spelling dictionary file not found: {missing}",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=missing,
                )
            if not self.available():
                raise BackendUnavailableError(
                    "Spylls is not available",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=self._root,
                )

            try:
                import spylls
                from spylls.hunspell import Dictionary

                engine = Dictionary.from_files(str(self._root))
                encoding = getattr(engine.aff, "SET", None)
                self._version = str(getattr(spylls, "__version__", "unknown"))
            except Exception as error:
                raise DictionaryLoadError(
                    f"Spylls could not load dictionary {self._root}",
                    backend=self.NAME,
                    operation="load_dictionary",
                    path=self._root,
                ) from error

            self._engine = engine
            self._encoding = str(encoding) if encoding else None

    def unload(self) -> None:
        with self._lock:
            self._engine = None
            self._encoding = None

    def check_word(self, word: str) -> bool:
        _validate_word(word)
        with self._lock:
            self.load_dictionary()
            engine = self._engine
            if engine is None:  # Defensive guard for alternative engine loaders.
                raise BackendUnavailableError(
                    "Spylls did not retain a loaded dictionary",
                    backend=self.NAME,
                    operation="check_word",
                    path=self._root,
                )
            try:
                return bool(engine.lookup(word))
            except Exception as error:
                raise BackendOperationError(
                    "Spylls failed to check a word",
                    backend=self.NAME,
                    operation="check_word",
                    path=self._root,
                ) from error

    def suggest(self, word: str, *, limit: int | None = 8) -> tuple[str, ...]:
        _validate_word(word)
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
            raise TypeError("limit must be an integer or None")
        if limit is not None and limit < 0:
            raise ValueError("limit must be zero or greater")
        if limit == 0:
            return ()

        with self._lock:
            self.load_dictionary()
            engine = self._engine
            if engine is None:  # Defensive guard for alternative engine loaders.
                raise BackendUnavailableError(
                    "Spylls did not retain a loaded dictionary",
                    backend=self.NAME,
                    operation="suggest",
                    path=self._root,
                )
            try:
                suggestions = engine.suggest(word)
                return tuple(suggestions if limit is None else islice(suggestions, limit))
            except Exception as error:
                raise BackendOperationError(
                    "Spylls failed to suggest corrections",
                    backend=self.NAME,
                    operation="suggest",
                    path=self._root,
                ) from error
