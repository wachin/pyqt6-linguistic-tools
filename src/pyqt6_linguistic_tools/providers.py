"""Dictionary source interfaces independent of linguistic engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import re
import shutil
import tempfile

from pyqt6_linguistic_tools.errors import (
    DictionaryDiscoveryError,
    DictionaryImportError,
)
from pyqt6_linguistic_tools.locales import (
    spelling_locale_from_stem,
    thesaurus_locale_from_stem,
)
from pyqt6_linguistic_tools.models import (
    DictionaryCandidate,
    DictionaryImportResult,
    DictionarySourcePriority,
    ValidationStatus,
)
from pyqt6_linguistic_tools.storage import dictionary_storage_paths


_SAFE_BUNDLE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _remove_owned_bundle(root: Path, bundle_name: str) -> bool:
    """Remove one direct, non-symlinked application-owned bundle."""
    if not isinstance(bundle_name, str):
        raise TypeError("bundle_name must be a string")
    if (
        not _SAFE_BUNDLE_NAME.fullmatch(bundle_name)
        or bundle_name in {".", ".."}
    ):
        raise ValueError("bundle_name must be one safe path component")
    target = root / bundle_name
    if target.is_symlink():
        raise DictionaryImportError("refusing to remove a symbolic-link bundle")
    if not target.exists():
        return False
    if not target.is_dir():
        raise DictionaryImportError("dictionary bundle must be a directory")
    shutil.rmtree(target)
    return True


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


class ManagedDictionaryProvider(DirectoryDictionaryProvider):
    """Discover application-managed dictionaries without downloading them."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        namespace: str = "pyqt6-linguistic-tools",
    ) -> None:
        managed_root = (
            Path(root).expanduser().resolve()
            if root is not None
            else dictionary_storage_paths(namespace).managed
        )
        super().__init__(
            managed_root,
            source="managed",
            priority=DictionarySourcePriority.MANAGED,
        )

    def discover(self) -> tuple[DictionaryCandidate, ...]:
        return () if not self.root.exists() else super().discover()

    def ensure_directory(self) -> Path:
        """Create the managed root only when explicitly requested."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def remove_bundle(self, bundle_name: str) -> bool:
        """Remove one direct application-managed bundle, never system data."""
        return _remove_owned_bundle(self.root, bundle_name)


class UserDictionaryProvider(DirectoryDictionaryProvider):
    """Discover and safely import user-supplied dictionary files."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        namespace: str = "pyqt6-linguistic-tools",
    ) -> None:
        user_root = (
            Path(root).expanduser().resolve()
            if root is not None
            else dictionary_storage_paths(namespace).user
        )
        super().__init__(
            user_root,
            source="user",
            priority=DictionarySourcePriority.USER,
        )

    def discover(self) -> tuple[DictionaryCandidate, ...]:
        return () if not self.root.exists() else super().discover()

    def ensure_directory(self) -> Path:
        """Create the user root only when explicitly requested."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def remove_bundle(self, bundle_name: str) -> bool:
        """Remove one direct manually imported bundle, never source files."""
        return _remove_owned_bundle(self.root, bundle_name)

    def import_files(
        self,
        files: tuple[str | Path, ...] | list[str | Path],
        *,
        bundle_name: str | None = None,
    ) -> Path:
        """Import a valid bundle and return its published directory."""
        return self.import_validated_files(
            files,
            bundle_name=bundle_name,
        ).destination

    def import_validated_files(
        self,
        files: tuple[str | Path, ...] | list[str | Path],
        *,
        bundle_name: str | None = None,
    ) -> DictionaryImportResult:
        """Atomically import one complete, previously unpacked dictionary bundle.

        Return the validation report that authorized publication. Existing
        bundles are never overwritten. Archive extraction and network access
        deliberately remain outside this method.
        """
        sources = tuple(Path(path).expanduser().resolve() for path in files)
        if not sources:
            raise DictionaryImportError("manual import requires at least one file")
        if any(not path.is_file() for path in sources):
            missing = next(path for path in sources if not path.is_file())
            raise DictionaryImportError(f"import source is not a file: {missing}")
        if len({path.name for path in sources}) != len(sources):
            raise DictionaryImportError("import contains duplicate filenames")
        allowed = {".aff", ".dic", ".dat", ".idx"}
        if any(path.suffix.lower() not in allowed for path in sources):
            raise DictionaryImportError("import contains an unsupported file type")

        self.ensure_directory()
        staging = Path(tempfile.mkdtemp(prefix=".import-", dir=self.root))
        published = False
        try:
            for source in sources:
                shutil.copy2(source, staging / source.name)
            candidates = DirectoryDictionaryProvider(
                staging,
                source=self.source,
                priority=self.priority,
                recursive=False,
            ).discover()
            recognized = {
                path.name
                for candidate in candidates
                for path in (
                    candidate.aff_path,
                    candidate.dic_path,
                    candidate.thesaurus_dat,
                    candidate.thesaurus_idx,
                )
                if path is not None
            }
            supplied = {path.name for path in sources}
            if not candidates or recognized != supplied:
                raise DictionaryImportError(
                    "import must contain complete Hunspell pairs and/or a valid MyThes data set"
                )

            # Import locally to keep provider discovery lightweight and avoid
            # loading either engine merely by constructing a provider.
            from pyqt6_linguistic_tools.validation import DictionaryValidator

            validation = DictionaryValidator().validate_candidates(candidates)
            if not validation.usable:
                failed = [
                    check.message
                    for report in validation.reports
                    for check in report.checks
                    if check.status is ValidationStatus.FAIL
                ]
                raise DictionaryImportError(
                    "dictionary validation failed: " + "; ".join(failed),
                    validation=validation,
                )

            selected_name = bundle_name or candidates[0].locale
            if (
                not isinstance(selected_name, str)
                or not _SAFE_BUNDLE_NAME.fullmatch(selected_name)
                or selected_name in {".", ".."}
            ):
                raise DictionaryImportError("bundle_name must be one safe path component")
            destination = self.root / selected_name
            if destination.exists():
                raise FileExistsError(f"dictionary bundle already exists: {destination}")
            os.replace(staging, destination)
            published = True
            return DictionaryImportResult(destination, validation)
        finally:
            if not published and staging.exists():
                shutil.rmtree(staging)


__all__ = [
    "DictionaryProvider",
    "DirectoryDictionaryProvider",
    "ManagedDictionaryProvider",
    "UserDictionaryProvider",
]
