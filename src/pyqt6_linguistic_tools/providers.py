"""Dictionary source interfaces independent of linguistic engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pyqt6_linguistic_tools.errors import DictionaryDiscoveryError
from pyqt6_linguistic_tools.locales import (
    spelling_locale_from_stem,
    thesaurus_locale_from_stem,
)
from pyqt6_linguistic_tools.models import DictionaryCandidate


class DictionaryProvider(ABC):
    """Enumerate dictionary candidates from one named, prioritized source."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Return the stable source identifier used in diagnostics."""

    @property
    @abstractmethod
    def priority(self) -> int:
        """Return precedence; a larger number wins component duplicates."""

    @abstractmethod
    def discover(self) -> tuple[DictionaryCandidate, ...]:
        """Return currently available dictionary candidates."""


class DirectoryDictionaryProvider(DictionaryProvider):
    """Discover Hunspell and MyThes pairs below a directory."""

    def __init__(
        self,
        root: str | Path,
        *,
        source: str,
        priority: int,
        recursive: bool = True,
    ) -> None:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise TypeError("priority must be an integer")
        if not isinstance(recursive, bool):
            raise TypeError("recursive must be a boolean")
        self._root = Path(root).expanduser().resolve()
        self._source = source.strip()
        self._priority = priority
        self._recursive = recursive

    @property
    def root(self) -> Path:
        return self._root

    @property
    def source(self) -> str:
        return self._source

    @property
    def priority(self) -> int:
        return self._priority

    def discover(self) -> tuple[DictionaryCandidate, ...]:
        if not self._root.is_dir():
            raise DictionaryDiscoveryError(
                f"dictionary directory does not exist: {self._root}",
                source=self.source,
                path=self._root,
            )

        files = self._root.rglob("*") if self._recursive else self._root.iterdir()
        # Preserve a symlink's own basename because Linux dictionary packages
        # commonly expose locale aliases as links to shared source files.
        paths = sorted(path.absolute() for path in files if path.is_file())
        by_stem: dict[tuple[Path, str], dict[str, Path]] = {}
        for path in paths:
            suffix = path.suffix.lower()
            if suffix not in {".aff", ".dic", ".dat", ".idx"}:
                continue
            stem = path.stem
            if suffix in {".dat", ".idx"} and not stem.lower().startswith("th_"):
                continue
            if suffix in {".aff", ".dic"} and stem.lower().startswith("hyph_"):
                continue
            by_stem.setdefault((path.parent, stem), {})[suffix] = path

        candidates: list[DictionaryCandidate] = []
        for (_, stem), components in sorted(
            by_stem.items(), key=lambda item: (str(item[0][0]), item[0][1])
        ):
            if ".aff" in components and ".dic" in components:
                candidates.append(
                    DictionaryCandidate(
                        locale=spelling_locale_from_stem(stem),
                        source=self.source,
                        priority=self.priority,
                        aff_path=components[".aff"],
                        dic_path=components[".dic"],
                    )
                )
            if ".dat" in components:
                candidates.append(
                    DictionaryCandidate(
                        locale=thesaurus_locale_from_stem(stem),
                        source=self.source,
                        priority=self.priority,
                        thesaurus_dat=components[".dat"],
                        thesaurus_idx=components.get(".idx"),
                    )
                )
        return tuple(candidates)


__all__ = ["DictionaryProvider", "DirectoryDictionaryProvider"]
