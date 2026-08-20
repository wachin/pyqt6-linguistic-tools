"""Cross-platform application data paths without changing Qt global state."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class DictionaryStoragePaths:
    """Shared root and separate managed/user dictionary locations."""

    root: Path
    managed: Path
    user: Path
    personal: Path


def _validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str):
        raise TypeError("namespace must be a string")
    namespace = namespace.strip()
    if (
        not namespace
        or namespace in {".", ".."}
        or Path(namespace).name != namespace
        or "/" in namespace
        or "\\" in namespace
    ):
        raise ValueError("namespace must be one safe path component")
    return namespace


def application_data_directory(
    namespace: str = "pyqt6-linguistic-tools",
    *,
    base_path: str | Path | None = None,
    prefer_qt: bool = True,
) -> Path:
    """Return an application data directory without creating it.

    `GenericDataLocation` is used instead of mutating `QCoreApplication` names,
    allowing ChordFlow and ChordPages to share one explicit namespace.
    """
    namespace = _validate_namespace(namespace)
    if base_path is not None:
        return (Path(base_path).expanduser().resolve() / namespace)
    if not isinstance(prefer_qt, bool):
        raise TypeError("prefer_qt must be a boolean")

    if prefer_qt:
        try:
            from PyQt6.QtCore import QStandardPaths

            location = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.GenericDataLocation
            )
            if location:
                return (Path(location).expanduser() / namespace).absolute()
        except (ImportError, AttributeError):
            pass

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base.expanduser() / namespace).absolute()


def dictionary_storage_paths(
    namespace: str = "pyqt6-linguistic-tools",
    *,
    base_path: str | Path | None = None,
    prefer_qt: bool = True,
) -> DictionaryStoragePaths:
    """Return conventional roots for managed and manually imported files."""
    root = application_data_directory(
        namespace,
        base_path=base_path,
        prefer_qt=prefer_qt,
    ) / "dictionaries"
    return DictionaryStoragePaths(
        root=root,
        managed=root / "managed",
        user=root / "user",
        personal=root / "personal",
    )


__all__ = [
    "DictionaryStoragePaths",
    "application_data_directory",
    "dictionary_storage_paths",
]
