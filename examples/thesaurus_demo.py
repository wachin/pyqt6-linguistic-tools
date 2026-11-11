"""Reusable thesaurus widget and dialog demo.

Shows how another PyQt6 application can use the toolkit as a package or as a
``libs/pyqt6-linguistic-tools`` git submodule:

- ``ThesaurusWidget`` embedded in a splitter next to an editor;
- ``ThesaurusDialog`` opened for the selected word;
- one shared ``LinguisticService`` for both.

Usage:
    python examples/thesaurus_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts \
        python examples/thesaurus_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import _bootstrap  # noqa: E402,F401

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt  # noqa: E402

from pyqt6_linguistic_tools import create_service  # noqa: E402
from pyqt6_linguistic_tools.qt import (  # noqa: E402
    LinguisticTextEditDecorator,
    ThesaurusDialog,
    ThesaurusWidget,
    install_toolkit_translations,
    require_pyqt6,
)


require_pyqt6()


class ThesaurusDemo(QMainWindow):
    """Embed the thesaurus widget and open the dialog for selected text."""

    def __init__(self, service) -> None:
        super().__init__()
        self._service = service
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Reusable Thesaurus Demo")
        self.resize(1000, 600)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Word:", central))
        self._word_input = QLineEdit(central)
        self._word_input.setPlaceholderText("feliz, presencia, bright…")
        self._word_input.returnPressed.connect(self._look_up)
        search_row.addWidget(self._word_input, 1)
        lookup_button = QPushButton("Look up", central)
        lookup_button.clicked.connect(self._look_up)
        search_row.addWidget(lookup_button)
        dialog_button = QPushButton("Open dialog", central)
        dialog_button.clicked.connect(self._open_dialog)
        search_row.addWidget(dialog_button)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self._editor = QTextEdit(splitter)
        self._editor.setPlainText(
            "Select a word such as presencia or feliz, then press Look up.\n\n"
            "The right side is the same ThesaurusWidget that an application "
            "can embed in a panel, tab or settings page."
        )
        splitter.addWidget(self._editor)

        self._thesaurus_widget = ThesaurusWidget(
            self._service,
            "feliz",
            parent=splitter,
        )
        splitter.addWidget(self._thesaurus_widget)
        splitter.setSizes([420, 580])
        layout.addWidget(splitter, 1)

        self._status_label = QLabel("Ready", central)
        layout.addWidget(self._status_label)

        self._decorator = LinguisticTextEditDecorator(
            self._editor,
            self._service,
        )

    def _current_word(self) -> str:
        word = self._word_input.text().strip()
        if word:
            return word
        cursor = self._editor.textCursor()
        return cursor.selectedText().strip()

    def _look_up(self) -> None:
        word = self._current_word()
        if not word:
            self._status_label.setText("Type a word or select one in the editor")
            return
        self._word_input.setText(word)
        self._thesaurus_widget.search(word)
        self._status_label.setText(f"Showing results for '{word}'")

    def _open_dialog(self) -> None:
        word = self._current_word()
        if not word:
            self._status_label.setText("Type a word or select one in the editor")
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
        else:
            self._status_label.setText("No editor selection to replace")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Reusable Thesaurus Demo")
    install_toolkit_translations(app, None)

    corpus = os.environ.get("LIBREOFFICE_DICTIONARIES_PATH")
    corpus_path = Path(corpus).expanduser() if corpus else None
    service = create_service(
        namespace="thesaurus-demo",
        corpus_path=corpus_path if corpus_path and corpus_path.is_dir() else None,
    )

    window = ThesaurusDemo(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
