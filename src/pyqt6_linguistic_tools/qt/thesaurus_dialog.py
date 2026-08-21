"""Reusable thesaurus browser with navigation and replacement signals."""

from __future__ import annotations

import unicodedata

from pyqt6_linguistic_tools.models import ThesaurusEntry
from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6.QtCore import QCoreApplication, Qt, pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


_TRANSLATION_CONTEXT = "PyQt6LinguisticTools.ThesaurusDialog"
_SYNONYM_ROLE = int(Qt.ItemDataRole.UserRole)


def _tr(text: str) -> str:
    return QCoreApplication.translate(_TRANSLATION_CONTEXT, text)


def preserve_simple_capitalization(source: str, replacement: str) -> str:
    """Transfer only unambiguous lower/title/upper casing to a replacement."""
    if not isinstance(source, str) or not isinstance(replacement, str):
        raise TypeError("source and replacement must be strings")
    source = unicodedata.normalize("NFC", source)
    replacement = unicodedata.normalize("NFC", replacement)
    if source.isupper():
        return replacement.upper()
    if source.istitle() and replacement.islower():
        return replacement[:1].upper() + replacement[1:]
    return replacement


class ThesaurusDialog(QDialog):
    """Display engine-neutral thesaurus entries without exposing PyThes."""

    query_changed = pyqtSignal(str)
    no_results = pyqtSignal(str)
    replacement_requested = pyqtSignal(str, str)

    def __init__(
        self,
        service: LinguisticService,
        word: str,
        *,
        replacement_source: str | None = None,
        locale: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if not isinstance(word, str):
            raise TypeError("word must be a string")
        if replacement_source is not None and not isinstance(replacement_source, str):
            raise TypeError("replacement_source must be a string or None")
        super().__init__(parent)
        self._service = service
        self._locale = normalize_locale(locale or service.language)
        self._replacement_source = replacement_source or word
        self._history: list[str] = []
        self._history_index = -1
        self._entry: ThesaurusEntry | None = None

        self.setWindowTitle(_tr("Thesaurus"))
        self.resize(620, 440)
        self._create_widgets()
        self.search(word)

    @property
    def service(self) -> LinguisticService:
        return self._service

    @property
    def query(self) -> str:
        return self.search_edit.text()

    @property
    def replacement_source(self) -> str:
        return self._replacement_source

    @property
    def locale(self) -> str:
        return self._locale

    @property
    def entry(self) -> ThesaurusEntry | None:
        return self._entry

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    @property
    def history_index(self) -> int:
        return self._history_index

    @property
    def selected_synonym(self) -> str | None:
        item = self.results.currentItem()
        if item is None:
            return None
        value = item.data(0, _SYNONYM_ROLE)
        return value if isinstance(value, str) and value else None

    def search(self, word: str, *, add_history: bool = True) -> bool:
        if not isinstance(word, str):
            raise TypeError("word must be a string")
        if not isinstance(add_history, bool):
            raise TypeError("add_history must be a boolean")
        word = unicodedata.normalize("NFC", word.strip())
        if not word:
            return False
        if add_history:
            del self._history[self._history_index + 1 :]
            if not self._history or self._history[-1] != word:
                self._history.append(word)
            self._history_index = len(self._history) - 1
        self.search_edit.setText(word)
        self.query_label.setText(_tr("Results for: %1").replace("%1", word))
        self._entry = self._service.thesaurus_entry(word, locale=self._locale)
        self._populate_results()
        self._update_navigation()
        self.query_changed.emit(word)
        return self._entry is not None

    def go_back(self) -> bool:
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self.search(self._history[self._history_index], add_history=False)
        return True

    def go_forward(self) -> bool:
        if self._history_index < 0 or self._history_index >= len(self._history) - 1:
            return False
        self._history_index += 1
        self.search(self._history[self._history_index], add_history=False)
        return True

    def search_selected(self) -> bool:
        synonym = self.selected_synonym
        return False if synonym is None else self.search(synonym)

    def replace_selected(self) -> bool:
        synonym = self.selected_synonym
        if synonym is None:
            return False
        replacement = preserve_simple_capitalization(
            self._replacement_source,
            synonym,
        )
        self.replacement_requested.emit(self._replacement_source, replacement)
        return True

    def _create_widgets(self) -> None:
        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.back_button = QPushButton(_tr("Back"), self)
        self.forward_button = QPushButton(_tr("Forward"), self)
        self.search_edit = QLineEdit(self)
        self.search_button = QPushButton(_tr("Search"), self)
        search_row.addWidget(self.back_button)
        search_row.addWidget(self.forward_button)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.query_label = QLabel(self)
        layout.addWidget(self.query_label)
        self.results = QTreeWidget(self)
        self.results.setHeaderLabels((_tr("Part of speech"), _tr("Meaning / synonym")))
        self.results.setRootIsDecorated(True)
        layout.addWidget(self.results, 1)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        action_row = QHBoxLayout()
        self.search_selected_button = QPushButton(_tr("Search Selected"), self)
        self.replace_button = QPushButton(_tr("Replace"), self)
        action_row.addWidget(self.search_selected_button)
        action_row.addStretch(1)
        action_row.addWidget(self.replace_button)
        layout.addLayout(action_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.back_button.clicked.connect(self.go_back)
        self.forward_button.clicked.connect(self.go_forward)
        self.search_button.clicked.connect(lambda: self.search(self.search_edit.text()))
        self.search_edit.returnPressed.connect(
            lambda: self.search(self.search_edit.text())
        )
        self.search_selected_button.clicked.connect(self.search_selected)
        self.replace_button.clicked.connect(self.replace_selected)
        self.results.itemSelectionChanged.connect(self._update_selection)
        self.results.itemDoubleClicked.connect(
            lambda _item, _column: self.search_selected()
        )

    def _populate_results(self) -> None:
        self.results.clear()
        if self._entry is None or not self._entry.meanings:
            word = self.search_edit.text()
            self.status_label.setText(
                _tr("No thesaurus entry found for “%1”.").replace("%1", word)
            )
            self.status_label.show()
            self.no_results.emit(word)
            self._update_selection()
            return
        self.status_label.clear()
        self.status_label.hide()
        for meaning in self._entry.meanings:
            parent = QTreeWidgetItem((meaning.part_of_speech, meaning.meaning))
            if meaning.meaning:
                parent.setData(0, _SYNONYM_ROLE, meaning.meaning)
            self.results.addTopLevelItem(parent)
            for synonym in meaning.synonyms:
                child = QTreeWidgetItem(("", synonym))
                child.setData(0, _SYNONYM_ROLE, synonym)
                parent.addChild(child)
            parent.setExpanded(True)
        self.results.resizeColumnToContents(0)
        self._update_selection()

    def _update_selection(self) -> None:
        enabled = self.selected_synonym is not None
        self.search_selected_button.setEnabled(enabled)
        self.replace_button.setEnabled(enabled)

    def _update_navigation(self) -> None:
        self.back_button.setEnabled(self._history_index > 0)
        self.forward_button.setEnabled(
            0 <= self._history_index < len(self._history) - 1
        )


__all__ = ["ThesaurusDialog", "preserve_simple_capitalization"]
