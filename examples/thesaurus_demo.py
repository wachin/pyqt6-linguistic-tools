"""Thesaurus browser demo using ThesaurusDialog.

Usage:
    python examples/thesaurus_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/thesaurus_demo.py
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
    QLineEdit,
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
    LinguisticTextEditDecorator,
    ThesaurusDialog,
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
    # Find a language with a thesaurus
    entries = registry.discover()
    for entry in entries:
        if entry.has_thesaurus:
            return entry.locale
    if entries:
        return entries[0].locale
    import locale as _locale

    lang, _encoding = _locale.getdefaultlocale()
    if lang:
        return normalize_locale(lang)
    return "en_US"


class ThesaurusDemo(QMainWindow):
    """Interactive demo showing thesaurus lookup."""

    def __init__(self, service: LinguisticService) -> None:
        super().__init__()
        self._service = service
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Thesaurus Demo")
        self.resize(600, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Search bar
        search_layout = QHBoxLayout()
        layout.addLayout(search_layout)

        search_layout.addWidget(QLabel("Word:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Type a word and press Enter")
        search_layout.addWidget(self._search_input)

        lookup_btn = QPushButton("Look Up")
        lookup_btn.clicked.connect(self._open_thesaurus)
        search_layout.addWidget(lookup_btn)

        # Editor for context
        editor_label = QLabel("Editor (select a word and click Look Up):")
        layout.addWidget(editor_label)

        self._editor = QTextEdit()
        self._editor.setPlainText(
            "Select a word in this text and click 'Look Up' to find synonyms.\n\n"
            "Example words: bright, happy, large, fast, begin, end, good, bad."
        )
        layout.addWidget(self._editor)

        self._decorator = LinguisticTextEditDecorator(self._editor, self._service)
        self._decorator.thesaurus_enabled = True

        # Status
        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def _open_thesaurus(self) -> None:
        word = self._search_input.text().strip()
        if not word:
            cursor = self._editor.textCursor()
            word = cursor.selectedText().strip()
        if not word:
            self._status_label.setText("Enter a word or select one in the editor")
            return

        dialog = ThesaurusDialog(self._service, word, parent=self)
        dialog.replacement_requested.connect(self._replace_word)
        dialog.exec()

    def _replace_word(self, _source: str, replacement: str) -> None:
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(replacement)
            self._editor.setTextCursor(cursor)
        self._status_label.setText(f"Replaced with '{replacement}'")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Thesaurus Demo")

    registry = _discover_registry()
    language = _pick_language(registry)
    service = LinguisticService(language, registry=registry)

    window = ThesaurusDemo(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())