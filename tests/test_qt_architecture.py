from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pyqt6_linguistic_tools.qt import (
    QtLinguisticSettings,
    QtRuntimeInfo,
    pyqt6_available,
    qt_runtime_info,
    require_pyqt6,
)


def test_core_and_qt_boundary_imports_do_not_eagerly_load_pyqt6():
    project = Path(__file__).resolve().parents[1]
    paths = (
        project / "src",
        project / "libs" / "spylls",
        project / "libs" / "pythes",
    )
    code = (
        "import json, sys; "
        f"sys.path[:0] = {list(map(str, paths))!r}; "
        "import pyqt6_linguistic_tools; "
        "core = sorted(name for name in sys.modules if name.startswith('PyQt6')); "
        "import pyqt6_linguistic_tools.qt; "
        "qt_boundary = sorted(name for name in sys.modules if name.startswith('PyQt6')); "
        "print(json.dumps([core, qt_boundary]))"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [[], []]


@pytest.mark.parametrize(
    "module",
    [
        "decorator",
        "spell_highlighter",
        "context_menu",
        "thesaurus_dialog",
        "dictionary_manager",
        "settings",
    ],
)
def test_planned_qt_components_have_stable_module_boundaries(module: str):
    imported = importlib.import_module(f"pyqt6_linguistic_tools.qt.{module}")

    assert imported.__package__ == "pyqt6_linguistic_tools.qt"


def test_qt_runtime_detection_is_explicit_and_reports_versions():
    if not pyqt6_available():
        pytest.skip("PyQt6 is an optional dependency")

    runtime = qt_runtime_info()

    assert isinstance(runtime, QtRuntimeInfo)
    assert runtime.qt_version
    assert runtime.pyqt_version
    assert require_pyqt6("6.0") == runtime


def test_qt_runtime_minimum_version_is_validated():
    with pytest.raises(ValueError, match="dot-separated integers"):
        require_pyqt6("six")


def test_qt_settings_defaults_match_architecture_budget():
    settings = QtLinguisticSettings()

    assert settings.spellcheck_enabled
    assert settings.highlighting_enabled
    assert settings.thesaurus_enabled
    assert settings.context_menu_enabled
    assert settings.suggestion_limit == 8
    assert settings.synonym_limit == 12
    assert settings.debounce_ms == 300


@pytest.mark.parametrize(
    "kwargs",
    [
        {"spellcheck_enabled": 1},
        {"highlighting_enabled": None},
        {"suggestion_limit": True},
        {"synonym_limit": -1},
        {"debounce_ms": 1.5},
    ],
)
def test_qt_settings_reject_invalid_values(kwargs):
    with pytest.raises((TypeError, ValueError)):
        QtLinguisticSettings(**kwargs)
