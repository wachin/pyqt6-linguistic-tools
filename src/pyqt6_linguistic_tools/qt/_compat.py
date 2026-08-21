"""Lazy PyQt6 detection without making Qt a core-package dependency."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


class QtIntegrationUnavailableError(ImportError):
    """PyQt6 is absent or older than the explicitly required version."""


@dataclass(frozen=True, slots=True)
class QtRuntimeInfo:
    """Versions observed only after the Qt layer explicitly requests PyQt6."""

    qt_version: str
    pyqt_version: str


def pyqt6_available() -> bool:
    """Return whether PyQt6 can be located without importing Qt modules."""
    try:
        return find_spec("PyQt6") is not None
    except (ImportError, ValueError):
        return False


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(component) for component in version.split("."))
    except (AttributeError, ValueError) as error:
        raise ValueError("minimum_version must contain dot-separated integers") from error


def qt_runtime_info() -> QtRuntimeInfo:
    """Import QtCore on demand and return stable runtime version strings."""
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    except (ImportError, ModuleNotFoundError) as error:
        raise QtIntegrationUnavailableError(
            "PyQt6 is required for pyqt6_linguistic_tools.qt widget features; "
            "install pyqt6-linguistic-tools[qt]"
        ) from error
    return QtRuntimeInfo(qt_version=QT_VERSION_STR, pyqt_version=PYQT_VERSION_STR)


def require_pyqt6(minimum_version: str = "6.6") -> QtRuntimeInfo:
    """Return runtime information or raise a stable optional-dependency error."""
    minimum = _version_tuple(minimum_version)
    runtime = qt_runtime_info()
    if _version_tuple(runtime.pyqt_version) < minimum:
        raise QtIntegrationUnavailableError(
            f"PyQt6 {minimum_version} or newer is required; "
            f"found {runtime.pyqt_version}"
        )
    return runtime


__all__ = [
    "QtIntegrationUnavailableError",
    "QtRuntimeInfo",
    "pyqt6_available",
    "qt_runtime_info",
    "require_pyqt6",
]
