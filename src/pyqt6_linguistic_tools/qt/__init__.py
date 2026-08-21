"""Optional PyQt6 integration boundary for the widget-independent core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyqt6_linguistic_tools.qt._compat import (
    QtIntegrationUnavailableError,
    QtRuntimeInfo,
    pyqt6_available,
    qt_runtime_info,
    require_pyqt6,
)
from pyqt6_linguistic_tools.qt.settings import QtLinguisticSettings

if TYPE_CHECKING:
    from pyqt6_linguistic_tools.qt.decorator import (
        ContextActionProvider,
        LinguisticTextEditDecorator,
    )


__all__ = [
    "ContextActionProvider",
    "LinguisticTextEditDecorator",
    "QtIntegrationUnavailableError",
    "QtLinguisticSettings",
    "QtRuntimeInfo",
    "pyqt6_available",
    "qt_runtime_info",
    "require_pyqt6",
]


def __getattr__(name: str) -> object:
    """Load widget classes only when applications explicitly request them."""
    if name in {"ContextActionProvider", "LinguisticTextEditDecorator"}:
        from pyqt6_linguistic_tools.qt import decorator

        return getattr(decorator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
