"""Add a pyqt6-linguistic-tools submodule checkout to ``sys.path``.

Use this when an application vendors the toolkit under ``libs/`` and does not
install it with pip::

    import sys
    from pathlib import Path

    toolkit = Path(__file__).resolve().parent / "libs" / "pyqt6-linguistic-tools"
    sys.path.insert(0, str(toolkit))
    import pyqt6_linguistic_tools_bootstrap  # noqa: F401

    from pyqt6_linguistic_tools import create_service

The module adds the package ``src`` directory and the two vendored engine
forks. It is intentionally outside the package so it can be imported before
``pyqt6_linguistic_tools`` exists on ``sys.path``.
"""

from __future__ import annotations

from pathlib import Path
import sys


TOOLKIT_ROOT = Path(__file__).resolve().parent
for _relative in ("src", "libs/spylls", "libs/pythes"):
    _path = str(TOOLKIT_ROOT / _relative)
    if _path not in sys.path:
        sys.path.insert(0, _path)
