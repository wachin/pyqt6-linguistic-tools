"""Make a source checkout runnable without installing the package."""

from __future__ import annotations

from pathlib import Path
import sys


TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
for _relative in ("src", "libs/spylls", "libs/pythes"):
    _path = str(TOOLKIT_ROOT / _relative)
    if _path not in sys.path:
        sys.path.insert(0, _path)
