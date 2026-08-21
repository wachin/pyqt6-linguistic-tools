"""Spell checking demo with suggestions, personal dictionary, and ignore words.

Usage:
    python examples/spellcheck_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/spellcheck_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QAction, QFont  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
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


class SpellCheckDemo(QMainWindow):
    """Interactive demo showing spell checking, suggestions, and personal words."""

    def __init__(self, service: LinguisticService) -> None:
        super().__init__()
        self._service = service
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Spell Check Demo")
        self.resize(800, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Editor with spell checking
        editor_label = QLabel("Editor with live spell checking:")
        layout.addWidget(editor_label)

        self._editor = QPlainTextEdit()
        self._editor.setPlainText(
            "Type text here. Misspelled words will be underlined in red.\n\n"
            "Examples: mispelled, recieve, thier, ocurrence, definately\n\n"
            "Right-click a misspelled word to see suggestions or add to your personal dictionary."
        )
        monospace = QFont("monospace", 12)
        self._editor.setFont(monospace)
        layout.addWidget(self._editor)

        self._decorator = LinguisticTextEditDecorator(self._editor, self._service)

        # Control panel
        controls = QHBoxLayout()
        layout.addLayout(controls)

        add_btn = QPushButton("Add Selected Word to Personal Dictionary")
        add_btn.clicked.connect(self._add_selected_word)
        controls.addWidget(add_btn)

        check_btn = QPushButton("Check Word")
        check_btn.clicked.connect(self._check_word)
        controls.addWidget(check_btn)

        toggle_btn = QPushButton("Toggle Spell Check")
        toggle_btn.clicked.connect(self._toggle_spell_check)
        controls.addWidget(toggle_btn)

        # Suggestions panel
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        suggestions_widget = QWidget()
        splitter.addWidget(suggestions_widget)
        s_layout = QVBoxLayout(suggestions_widget)
        s_layout.setContentsMargins(0, 0, 0, 0)

        s_label = QLabel("Suggestions:")
        s_layout.addWidget(s_label)

        self._suggestions_list = QListWidget()
        s_layout.addWidget(self._suggestions_list)

        # Status
        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def _add_selected_word(self) -> None:
        cursor = self._editor.textCursor()
        word = cursor.selectedText()
        if word:
            self._service.add_to_personal_dictionary(word)
            self._status_label.setText(f"Added '{word}' to personal dictionary")

    def _check_word(self) -> None:
        cursor = self._editor.textCursor()
        word = cursor.selectedText()
        if not word:
            self._status_label.setText("Select a word first")
            return
        accepted = self._service.check_word(word)
        if accepted:
            self._status_label.setText(f"'{word}' is spelled correctly")
        else:
            suggestions = self._service.suggestions(word)
            self._suggestions_list.clear()
            if suggestions:
                self._suggestions_list.addItems(suggestions)
                self._status_label.setText(
                    f"'{word}' is misspelled — {len(suggestions)} suggestion(s)"
                )
            else:
                self._status_label.setText(f"'{word}' is misspelled — no suggestions")

    def _toggle_spell_check(self) -> None:
        enabled = not self._service.spell_check_enabled
        self._service.set_spell_check_enabled(enabled)
        self._status_label.setText(
            f"Spell check {'enabled' if enabled else 'disabled'}"
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Spell Check Demo")

    registry = _discover_registry()
    language = _pick_language(registry)
    service = LinguisticService(language, registry=registry)

    window = SpellCheckDemo(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())