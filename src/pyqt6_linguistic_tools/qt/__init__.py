"""Optional PyQt6 integration boundary for the widget-independent core."""

from pyqt6_linguistic_tools.qt._compat import (
    QtIntegrationUnavailableError,
    QtRuntimeInfo,
    pyqt6_available,
    qt_runtime_info,
    require_pyqt6,
)
from pyqt6_linguistic_tools.qt.settings import QtLinguisticSettings


__all__ = [
    "QtIntegrationUnavailableError",
    "QtLinguisticSettings",
    "QtRuntimeInfo",
    "pyqt6_available",
    "qt_runtime_info",
    "require_pyqt6",
]
