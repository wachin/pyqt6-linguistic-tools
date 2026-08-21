"""Full-featured demo combining all toolkit features.

Shows how a PyQt6 application can integrate the full linguistic toolkit
with minimal code. Combines a spell-checking editor, thesaurus, dictionary
manager, language switching, and personal dictionary management.

Usage:
    python examples/full_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/full_demo.py
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
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QStatusBar,
    QToolBar,
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


class FullDemo(QMainWindow):
    """Application integrating all toolkit features."""

    def __init__(self, service: LinguisticService) -> None:
        super().__init__()
        self._service = service
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Linguistic Tools — Full Demo")
        self.resize(800, 600)

        # Central editor
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("monospace", 12))
        self._editor.setPlainText(
            "Welcome to the Linguistic Tools demo!\n\n"
            "This editor has full spell checking, thesaurus, and dictionary management.\n\n"
            "Try typing misspelled words like:\n"
            "  - mispelled\n"
            "  - recieve\n"
            "  - thier\n\n"
            "Right-click on a misspelled word to see suggestions, add to personal\n"
            "dictionary, or ignore it.\n\n"
            "Use the toolbar to look up synonyms or manage dictionaries.\n"
            "Use the language menu to switch between available languages."
        )
        self.setCentralWidget(self._editor)

        # Attach the decorator
        self._decorator = LinguisticTextEditDecorator(self._editor, self._service)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._update_status()

    def _setup_menus(self) -> None:
        menubar = self.menuBar()
        assert menubar is not None

        # File menu
        file_menu = menubar.addMenu("&File")
        assert file_menu is not None

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        assert tools_menu is not None

        thesaurus_action = QAction("&Thesaurus", self)
        thesaurus_action.setShortcut("Ctrl+T")
        thesaurus_action.triggered.connect(self._open_thesaurus)
        tools_menu.addAction(thesaurus_action)

        dict_action = QAction("&Dictionary Manager", self)
        dict_action.setShortcut("Ctrl+D")
        dict_action.triggered.connect(self._open_dictionary_manager)
        tools_menu.addAction(dict_action)

        tools_menu.addSeparator()

        add_word_action = QAction("Add Word to &Personal Dictionary", self)
        add_word_action.setShortcut("Ctrl+P")
        add_word_action.triggered.connect(self._add_personal_word)
        tools_menu.addAction(add_word_action)

        # Language menu
        self._language_menu = menubar.addMenu("&Language")
        assert self._language_menu is not None
        self._refresh_language_menu()

        # Help menu
        help_menu = menubar.addMenu("&Help")
        assert help_menu is not None

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        # Language selector
        toolbar.addWidget(QLabel("Language:"))
        self._lang_combo = QComboBox()
        self._lang_combo.setMinimumWidth(120)
        available = self._service.available_languages()
        for lang in available:
            self._lang_combo.addItem(lang, lang)
        current = self._service.language
        if current in available:
            self._lang_combo.setCurrentText(current)
        self._lang_combo.currentTextChanged.connect(self._switch_language)
        toolbar.addWidget(self._lang_combo)

        toolbar.addSeparator()

        thesaurus_btn = toolbar.addAction("Thesaurus")
        assert thesaurus_btn is not None
        thesaurus_btn.triggered.connect(self._open_thesaurus)

        dict_btn = toolbar.addAction("Dictionaries")
        assert dict_btn is not None
        dict_btn.triggered.connect(self._open_dictionary_manager)

    def _refresh_language_menu(self) -> None:
        assert self._language_menu is not None
        self._language_menu.clear()
        available = self._service.available_languages()
        for lang in available:
            action = QAction(lang, self)
            action.setCheckable(True)
            action.setChecked(lang == self._service.language)
            action.triggered.connect(lambda _checked, l=lang: self._switch_language(l))
            self._language_menu.addAction(action)

    def _switch_language(self, language: str) -> None:
        self._service.set_language(language)
        self._lang_combo.setCurrentText(language)
        self._refresh_language_menu()
        self._update_status()

    def _open_thesaurus(self) -> None:
        cursor = self._editor.textCursor()
        word = cursor.selectedText().strip()
        if not word:
            self._status.showMessage("Select a word first", 3000)
            return

        dialog = ThesaurusDialog(self._service, word, parent=self)
        dialog.replacement_requested.connect(self._replace_word)
        dialog.exec()
        self._update_status()

    def _replace_word(self, _source: str, replacement: str) -> None:
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(replacement)
            self._editor.setTextCursor(cursor)
            self._status.showMessage(f"Replaced with '{replacement}'", 3000)

    def _open_dictionary_manager(self) -> None:
        DictionaryManagerDialog(self._service, parent=self).exec()
        self._refresh_language_menu()
        self._update_status()

    def _add_personal_word(self) -> None:
        cursor = self._editor.textCursor()
        word = cursor.selectedText().strip()
        if word:
            self._service.add_to_personal_dictionary(word)
            self._status.showMessage(f"Added '{word}' to personal dictionary", 3000)
        else:
            self._status.showMessage("Select a word first", 3000)

    def _update_status(self) -> None:
        caps = self._service.capabilities()
        self._status.showMessage(
            f"Language: {self._service.language} | "
            f"Spell check: {'on' if caps.spell_check else 'off'} | "
            f"Thesaurus: {'on' if caps.thesaurus else 'off'}"
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Linguistic Tools Demo",
            "PyQt6 Linguistic Tools — Full Demo\n\n"
            "Demonstrates the complete toolkit integration:\n"
            "• Spell checking with highlighting\n"
            "• Spelling suggestions\n"
            "• Personal dictionary\n"
            "• Thesaurus/synonyms\n"
            "• Dictionary management\n"
            "• Language switching\n\n"
            "Part of the GuitarChordStudio project.",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Linguistic Tools Demo")

    registry = _discover_registry()
    service = LinguisticService(
        "en_US",
        registry=registry,
    )

    # If no dictionaries are available, show a warning
    available = service.available_languages()
    if not available:
        msg = (
            "No dictionaries found.\n\n"
            "To use system dictionaries, install hunspell-* and mythes-* packages.\n"
            "To use a LibreOffice corpus, set LIBREOFFICE_DICTIONARIES_PATH."
        )
        QMessageBox.warning(None, "No Dictionaries", msg)

    window = FullDemo(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())