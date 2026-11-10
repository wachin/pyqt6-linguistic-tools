"""Reusable thesaurus browser with navigation and replacement signals."""

from __future__ import annotations

from dataclasses import dataclass
import html
import unicodedata

from pyqt6_linguistic_tools.models import ThesaurusEntry, ThesaurusMeaning
from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6.QtCore import (  # noqa: E402
    QByteArray,
    QCoreApplication,
    QMimeData,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


_SYNONYM_ROLE = int(Qt.ItemDataRole.UserRole)


def _meaning_part_of_speech(value: str) -> str:
    """Normalize MyThes placeholders such as ``-`` to an empty category."""
    category = (value or "").strip()
    return "" if category in {"", "-", "?", "—", "–"} else category


def _meaning_heading(meaning: ThesaurusMeaning) -> str:
    category = _meaning_part_of_speech(meaning.part_of_speech)
    if category and meaning.meaning:
        return f"{category} — {meaning.meaning}"
    return category or meaning.meaning


def _escape_html(value: str) -> str:
    return html.escape(value, quote=False)


def _escape_markdown(value: str) -> str:
    for character in ("\\", "*", "_", "`", "[", "]"):
        value = value.replace(character, "\\" + character)
    return value


def _escape_rtf(value: str) -> str:
    result: list[str] = []
    for character in value:
        code = ord(character)
        if character in "\\{}":
            result.append("\\" + character)
        elif character == "\n":
            result.append("\\par ")
        elif code < 128:
            result.append(character)
        elif code <= 0xFFFF:
            signed = code if code < 0x8000 else code - 0x10000
            result.append(f"\\u{signed}?")
        else:
            result.append("?")
    return "".join(result)


@dataclass(frozen=True, slots=True)
class ThesaurusClipboardFormats:
    """Rich and Markdown representations of one thesaurus result."""

    html: str
    rtf: str
    markdown: str


def thesaurus_clipboard_formats(
    entry: ThesaurusEntry,
    word: str,
) -> ThesaurusClipboardFormats:
    """Build clipboard formats with bold meaning groups and synonym bullets."""
    title = word.strip() or entry.word
    html_parts = ["<html><body>"]
    markdown_parts: list[str] = []
    rtf_parts = ["{\\rtf1\\ansi\\deff0"]
    if title:
        html_parts.append(f"<p><b>{_escape_html(title)}</b></p>")
        markdown_parts.extend([f"**{_escape_markdown(title)}**", ""])
        rtf_parts.append(f"\\pard\\b {_escape_rtf(title)}\\b0\\par")
    for meaning in entry.meanings:
        heading = _meaning_heading(meaning)
        if heading:
            html_parts.append(f"<p><b>{_escape_html(heading)}</b></p>")
            markdown_parts.extend([f"**{_escape_markdown(heading)}**", ""])
            rtf_parts.append(f"\\pard\\b {_escape_rtf(heading)}\\b0\\par")
        if meaning.synonyms:
            html_parts.append("<ul>")
            for synonym in meaning.synonyms:
                html_parts.append(f"<li>{_escape_html(synonym)}</li>")
                markdown_parts.append(f"- {_escape_markdown(synonym)}")
                rtf_parts.append(f"\\pard\\bullet\\tab {_escape_rtf(synonym)}\\par")
            html_parts.append("</ul>")
            markdown_parts.append("")
            rtf_parts.append("\\par")
    html_parts.append("</body></html>")
    rtf_parts.append("}")
    markdown = "\n".join(markdown_parts).strip()
    if markdown:
        markdown += "\n"
    return ThesaurusClipboardFormats(
        html="\n".join(html_parts),
        rtf="\n".join(rtf_parts),
        markdown=markdown,
    )


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


class ThesaurusWidget(QWidget):
    """Embeddable thesaurus browser without exposing PyThes."""

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
    def language(self) -> str:
        """Return the linguistic locale without overriding QWidget.locale()."""
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
        self.query_label.setText(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Results for: %1"
            ).replace("%1", word)
        )
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
        self.back_button = QPushButton(
            QCoreApplication.translate("PyQt6LinguisticTools.ThesaurusDialog", "Back"),
            self,
        )
        self.forward_button = QPushButton(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Forward"
            ),
            self,
        )
        self.search_edit = QLineEdit(self)
        self.search_button = QPushButton(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Search"
            ),
            self,
        )
        search_row.addWidget(self.back_button)
        search_row.addWidget(self.forward_button)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.query_label = QLabel(self)
        layout.addWidget(self.query_label)
        self.results = QTreeWidget(self)
        self.results.setHeaderLabels(
            (
                QCoreApplication.translate(
                    "PyQt6LinguisticTools.ThesaurusDialog", "Part of speech"
                ),
                QCoreApplication.translate(
                    "PyQt6LinguisticTools.ThesaurusDialog", "Meaning / synonym"
                ),
            )
        )
        self.results.setRootIsDecorated(True)
        layout.addWidget(self.results, 1)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        action_row = QHBoxLayout()
        self.search_selected_button = QPushButton(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Search Selected"
            ),
            self,
        )
        self.replace_button = QPushButton(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Replace"
            ),
            self,
        )
        action_row.addWidget(self.search_selected_button)
        self.copy_button = QPushButton(
            QCoreApplication.translate("PyQt6LinguisticTools.ThesaurusDialog", "Copy"),
            self,
        )
        self.copy_button.setToolTip(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog",
                "Copy the results as rich text and Markdown.",
            )
        )
        self.copy_button.setEnabled(False)
        action_row.addWidget(self.copy_button)
        action_row.addStretch(1)
        action_row.addWidget(self.replace_button)
        layout.addLayout(action_row)

        self.back_button.clicked.connect(self.go_back)
        self.forward_button.clicked.connect(self.go_forward)
        self.search_button.clicked.connect(lambda: self.search(self.search_edit.text()))
        self.search_edit.returnPressed.connect(
            lambda: self.search(self.search_edit.text())
        )
        self.search_selected_button.clicked.connect(self.search_selected)
        self.replace_button.clicked.connect(self.replace_selected)
        self.copy_button.clicked.connect(self.copy_results)
        self.results.itemSelectionChanged.connect(self._update_selection)
        self.results.itemDoubleClicked.connect(
            lambda _item, _column: self.search_selected()
        )

    @staticmethod
    def _meaning_part_of_speech(value: str) -> str:
        return _meaning_part_of_speech(value)

    @staticmethod
    def _bold_item(item: QTreeWidgetItem, column: int) -> None:
        font = item.font(column)
        font.setBold(True)
        item.setFont(column, font)

    def copy_results(self) -> None:
        """Copy the result as rich text and Markdown in one clipboard action."""
        entry = self._entry
        if entry is None or not entry.meanings:
            return
        formats = thesaurus_clipboard_formats(entry, self.query)
        mime = QMimeData()
        mime.setHtml(formats.html)
        mime.setData(
            "text/rtf",
            QByteArray(formats.rtf.encode("ascii", "replace")),
        )
        mime.setText(formats.markdown)
        mime.setData(
            "text/markdown",
            QByteArray(formats.markdown.encode("utf-8")),
        )
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setMimeData(mime)
        self._show_copy_feedback(entry)

    def _show_copy_feedback(self, entry: ThesaurusEntry) -> None:
        previous_text = self.status_label.text()
        previous_visible = self.status_label.isVisible()
        query = self.query
        self.status_label.setText(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog",
                "Copied to clipboard.",
            )
        )
        self.status_label.show()

        def restore() -> None:
            if self._entry is entry and self.query == query:
                self.status_label.setText(previous_text)
                self.status_label.setVisible(previous_visible)

        QTimer.singleShot(2000, restore)

    def _populate_results(self) -> None:
        self.results.clear()
        if self._entry is None or not self._entry.meanings:
            self.copy_button.setEnabled(False)
            self.results.setColumnHidden(0, False)
            word = self.search_edit.text()
            self.status_label.setText(
                QCoreApplication.translate(
                    "PyQt6LinguisticTools.ThesaurusDialog",
                    "No thesaurus entry found for “%1”.",
                ).replace("%1", word)
            )
            self.status_label.show()
            self.no_results.emit(word)
            self._update_selection()
            return
        meanings = self._entry.meanings
        has_categories = any(
            self._meaning_part_of_speech(meaning.part_of_speech) for meaning in meanings
        )
        header = self.results.header()
        if has_categories:
            self.results.setHeaderLabels(
                (
                    QCoreApplication.translate(
                        "PyQt6LinguisticTools.ThesaurusDialog", "Part of speech"
                    ),
                    QCoreApplication.translate(
                        "PyQt6LinguisticTools.ThesaurusDialog",
                        "Meaning / synonym",
                    ),
                )
            )
            self.results.setColumnHidden(0, False)
            self.results.setColumnHidden(1, False)
            if header is not None:
                header.setStretchLastSection(True)
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        else:
            # With no POS metadata, use one visible column so the tree branch
            # and indentation remain visible. The meaning is the bold group
            # heading and its synonyms are the indented children.
            self.results.setHeaderLabels(
                (
                    QCoreApplication.translate(
                        "PyQt6LinguisticTools.ThesaurusDialog",
                        "Meaning / synonym",
                    ),
                    "",
                )
            )
            self.results.setColumnHidden(0, False)
            self.results.setColumnHidden(1, True)
            if header is not None:
                header.setStretchLastSection(False)
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.status_label.clear()
        self.status_label.hide()
        for meaning in meanings:
            if has_categories:
                parent = QTreeWidgetItem(
                    (
                        self._meaning_part_of_speech(meaning.part_of_speech),
                        meaning.meaning,
                    )
                )
                for column in (0, 1):
                    self._bold_item(parent, column)
            else:
                parent = QTreeWidgetItem((meaning.meaning, ""))
                self._bold_item(parent, 0)
            if meaning.meaning:
                parent.setData(0, _SYNONYM_ROLE, meaning.meaning)
            self.results.addTopLevelItem(parent)
            for synonym in meaning.synonyms:
                child = (
                    QTreeWidgetItem(("", synonym))
                    if has_categories
                    else QTreeWidgetItem((synonym, ""))
                )
                child.setData(0, _SYNONYM_ROLE, synonym)
                parent.addChild(child)
            parent.setExpanded(True)
        self.copy_button.setEnabled(bool(meanings))
        if not has_categories:
            self.status_label.setText(
                QCoreApplication.translate(
                    "PyQt6LinguisticTools.ThesaurusDialog",
                    "This dictionary does not provide grammatical categories.",
                )
            )
            self.status_label.show()
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


class ThesaurusDialog(QDialog):
    """Dialog wrapper around :class:`ThesaurusWidget`.

    Applications that want a panel instead of a window can embed
    :class:`ThesaurusWidget` directly and connect the same signals.
    """

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
        super().__init__(parent)
        self._widget = ThesaurusWidget(
            service,
            word,
            replacement_source=replacement_source,
            locale=locale,
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setWindowTitle(
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Thesaurus"
            )
        )
        self.resize(620, 440)
        self._widget.query_changed.connect(self.query_changed.emit)
        self._widget.no_results.connect(self.no_results.emit)
        self._widget.replacement_requested.connect(self.replacement_requested.emit)

    @property
    def widget(self) -> ThesaurusWidget:
        return self._widget

    @property
    def service(self) -> LinguisticService:
        return self._widget.service

    @property
    def query(self) -> str:
        return self._widget.query

    @property
    def replacement_source(self) -> str:
        return self._widget.replacement_source

    @property
    def language(self) -> str:
        return self._widget.language

    @property
    def entry(self) -> ThesaurusEntry | None:
        return self._widget.entry

    @property
    def history(self) -> tuple[str, ...]:
        return self._widget.history

    @property
    def history_index(self) -> int:
        return self._widget.history_index

    @property
    def selected_synonym(self) -> str | None:
        return self._widget.selected_synonym

    @property
    def results(self) -> QTreeWidget:
        return self._widget.results

    @property
    def search_edit(self) -> QLineEdit:
        return self._widget.search_edit

    @property
    def status_label(self) -> QLabel:
        return self._widget.status_label

    @property
    def query_label(self) -> QLabel:
        return self._widget.query_label

    @property
    def back_button(self) -> QPushButton:
        return self._widget.back_button

    @property
    def forward_button(self) -> QPushButton:
        return self._widget.forward_button

    @property
    def search_button(self) -> QPushButton:
        return self._widget.search_button

    @property
    def search_selected_button(self) -> QPushButton:
        return self._widget.search_selected_button

    @property
    def replace_button(self) -> QPushButton:
        return self._widget.replace_button

    @property
    def copy_button(self) -> QPushButton:
        return self._widget.copy_button

    def search(self, word: str, *, add_history: bool = True) -> bool:
        return self._widget.search(word, add_history=add_history)

    def go_back(self) -> bool:
        return self._widget.go_back()

    def go_forward(self) -> bool:
        return self._widget.go_forward()

    def search_selected(self) -> bool:
        return self._widget.search_selected()

    def replace_selected(self) -> bool:
        return self._widget.replace_selected()

    def copy_results(self) -> None:
        self._widget.copy_results()


__all__ = [
    "ThesaurusDialog",
    "ThesaurusWidget",
    "preserve_simple_capitalization",
]
