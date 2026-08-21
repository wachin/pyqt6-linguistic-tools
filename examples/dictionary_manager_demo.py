"""Dictionary Manager dialog demo.

Shows the DictionaryManagerDialog for inspecting and importing dictionaries.

Usage:
    python examples/dictionary_manager_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/dictionary_manager_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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
    DictionaryManagerDialog,
    LinguisticTextEditDecorator,
    require_pyqt6,
)


require_pyqt6()


def _discover_registry() -> DictionaryRegistry:
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
    entries = registry.discover()
    if entries:
        return entries[0].locale
    import locale as _locale

    lang, _encoding = _locale.getdefaultlocale()
    if lang:
        return normalize_locale(lang)
    return "en_US"


class DictionaryManagerDemo(QMainWindow):
    """Demo showing the DictionaryManagerDialog."""

    def __init__(self, service: LinguisticService) -> None:
        super().__init__()
        self._service = service
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Dictionary Manager Demo")
        self.resize(600, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        label = QLabel(
            "Click the button below to open the Dictionary Manager.\n"
            "It shows installed dictionaries and allows importing new ones."
        )
        layout.addWidget(label)

        open_btn = QPushButton("Open Dictionary Manager")
        open_btn.clicked.connect(self._open_manager)
        layout.addWidget(open_btn)

        self._editor = QTextEdit()
        self._editor.setPlainText(
            "Editor with spell checking — open the Dictionary Manager\n"
            "to see available dictionaries and manage imports."
        )
        layout.addWidget(self._editor)

        self._decorator = LinguisticTextEditDecorator(self._editor, self._service)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def _open_manager(self) -> None:
        dialog = DictionaryManagerDialog(self._service, parent=self)
        dialog.exec()
        self._status_label.setText("Dictionary Manager closed")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Dictionary Manager Demo")

    registry = _discover_registry()
    language = _pick_language(registry)
    service = LinguisticService(language, registry=registry)

    window = DictionaryManagerDemo(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())