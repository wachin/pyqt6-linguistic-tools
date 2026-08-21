"""Minimal QTextEdit integration with spell checking and highlighting.

Usage:
    python examples/basic_qtextedit.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/basic_qtextedit.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit  # noqa: E402

from pyqt6_linguistic_tools import (  # noqa: E402
    DEFAULT_LINUX_DICTIONARY_PATHS,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
    normalize_locale,
)
from pyqt6_linguistic_tools.qt import (  # noqa: E402
    LinguisticTextEditDecorator,
    require_pyqt6,
)


require_pyqt6()


def _discover_registry() -> DictionaryRegistry:
    """Build a registry with available dictionary sources."""
    providers: list = [LinuxSystemDictionaryProvider()]

    corpus = os.environ.get("LIBREOFFICE_DICTIONARIES_PATH")
    if corpus:
        corpus_path = Path(corpus).expanduser().resolve()
        if corpus_path.is_dir():
            providers.append(
                DirectoryDictionaryProvider(
                    corpus_path,
                    source="corpus",
                    priority=DictionarySourcePriority.MANAGED,
                )
            )

    providers.extend(
        [
            ManagedDictionaryProvider(),
            UserDictionaryProvider(),
        ]
    )
    return DictionaryRegistry(tuple(providers))


def _pick_language(registry: DictionaryRegistry) -> str:
    """Return the first available language or a fallback."""
    entries = registry.discover()
    if entries:
        return entries[0].locale
    # Fall back to the system locale language
    import locale as _locale

    lang, _encoding = _locale.getdefaultlocale()
    if lang:
        return normalize_locale(lang)
    return "en_US"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LinguisticTools QTextEdit Example")

    registry = _discover_registry()
    language = _pick_language(registry)
    service = LinguisticService(language, registry=registry)

    window = QMainWindow()
    window.setWindowTitle(
        f"QTextEdit — {service.available_languages()[0] if service.available_languages() else language}"
    )
    window.resize(600, 400)

    editor = QTextEdit()
    editor.setPlainText(
        "Type here to test spell checking.\n\n"
        "Misspelled wirds wil be highlighted.\n\n"
        "Right-click on a misspelled word to see suggestions."
    )
    window.setCentralWidget(editor)

    decorator = LinguisticTextEditDecorator(editor, service)
    _ = decorator  # keep reference

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())