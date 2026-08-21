"""Non-destructive, bounded linguistic context-menu integration."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pyqt6_linguistic_tools.locales import locale_display_name
from pyqt6_linguistic_tools.qt._compat import require_pyqt6
from pyqt6_linguistic_tools.qt.thesaurus_dialog import ThesaurusDialog

if TYPE_CHECKING:
    from pyqt6_linguistic_tools.qt.decorator import LinguisticTextEditDecorator


require_pyqt6()

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, Qt, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QAction, QContextMenuEvent, QTextCursor  # noqa: E402
from PyQt6.QtWidgets import QMenu  # noqa: E402


_TRANSLATION_CONTEXT = "PyQt6LinguisticTools"


def _tr(text: str) -> str:
    return QCoreApplication.translate(_TRANSLATION_CONTEXT, text)


class LinguisticAction(StrEnum):
    SUGGESTIONS = "suggestions"
    IGNORE = "ignore"
    IGNORE_ALL = "ignore_all"
    ADD_TO_DICTIONARY = "add_to_dictionary"
    SYNONYMS = "synonyms"
    OPEN_THESAURUS = "open_thesaurus"
    LANGUAGE = "language"


class LinguisticContextMenu(QObject):
    """Add linguistic actions while leaving the host's standard actions intact."""

    open_thesaurus_requested = pyqtSignal(str)
    more_synonyms_requested = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    word_ignored = pyqtSignal(str, bool)
    word_added_to_dictionary = pyqtSignal(str)

    def __init__(
        self,
        integration: LinguisticTextEditDecorator,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._integration = integration
        self._action_enabled = {action: True for action in LinguisticAction}
        self._dialogs: set[ThesaurusDialog] = set()

    def action_enabled(self, action: LinguisticAction | str) -> bool:
        return self._action_enabled[self._coerce_action(action)]

    def set_action_enabled(
        self, action: LinguisticAction | str, enabled: bool
    ) -> bool:
        action = self._coerce_action(action)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        if self._action_enabled[action] == enabled:
            return False
        self._action_enabled[action] = enabled
        return True

    def create_menu(self, cursor: QTextCursor | None = None) -> QMenu:
        """Return a standard editor menu augmented with linguistic actions."""
        editor = self._integration.editor
        if editor is None:
            raise RuntimeError("the linguistic integration is detached")
        if cursor is None:
            cursor = editor.textCursor()
        elif not isinstance(cursor, QTextCursor):
            raise TypeError("cursor must be a QTextCursor or None")
        menu = editor.createStandardContextMenu()
        existing = set(menu.actions())
        for action in editor.actions():
            if action not in existing:
                menu.addAction(action)
        self.populate_menu(menu, cursor)
        return menu

    def populate_menu(self, menu: QMenu, cursor: QTextCursor) -> int:
        """Append enabled actions to a host-created menu and return their count."""
        if not isinstance(menu, QMenu):
            raise TypeError("menu must be a QMenu")
        if not isinstance(cursor, QTextCursor):
            raise TypeError("cursor must be a QTextCursor")
        integration = self._integration
        token = integration.word_at_cursor(cursor)
        added = 0
        if token is not None:
            correct = integration.check_word_at_cursor(cursor)
            if correct is False:
                added += self._add_spelling_actions(
                    menu,
                    cursor,
                    token.text,
                    token.utf16_start,
                )
            if integration.thesaurus_active:
                added += self._add_thesaurus_actions(menu, cursor, token.text)
        added += self._add_language_menu(menu)
        added += self._add_host_provider_actions(menu, token)
        return added

    def handle_event(self, watched: QObject, event: object) -> bool:
        """Show an augmented default menu; custom-policy menus remain host-owned."""
        integration = self._integration
        editor = integration.editor
        if (
            editor is None
            or not integration.context_menu_active
            or not isinstance(event, QContextMenuEvent)
            or event.type() != QEvent.Type.ContextMenu
            or editor.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        ):
            return False
        viewport = editor.viewport()
        position = event.pos()
        if watched is editor:
            position = viewport.mapFrom(editor, position)
        cursor = editor.cursorForPosition(position)
        menu = self.create_menu(cursor)
        menu.exec(event.globalPos())
        menu.deleteLater()
        return True

    def _add_spelling_actions(
        self,
        menu: QMenu,
        cursor: QTextCursor,
        word: str,
        occurrence_id: int,
    ) -> int:
        integration = self._integration
        count = 0
        if self.action_enabled(LinguisticAction.SUGGESTIONS):
            suggestions = integration.suggestions_at_cursor(
                cursor,
                limit=integration.settings.suggestion_limit,
            )
            if suggestions:
                menu.addSeparator()
                for suggestion in suggestions:
                    action = menu.addAction(suggestion)
                    action.triggered.connect(
                        lambda _checked=False, value=suggestion: (
                            integration.replace_word_at_cursor(
                                value,
                                cursor,
                                expected_word=word,
                            )
                        )
                    )
                    count += 1
            else:
                menu.addSeparator()
                action = menu.addAction(_tr("No spelling suggestions"))
                action.setEnabled(False)
                count += 1
        scope_actions = []
        if self.action_enabled(LinguisticAction.IGNORE):
            action = QAction(_tr("Ignore"), menu)
            action.triggered.connect(
                lambda: self._ignore_word(word, occurrence_id, all_occurrences=False)
            )
            scope_actions.append(action)
        if self.action_enabled(LinguisticAction.IGNORE_ALL):
            action = QAction(_tr("Ignore All"), menu)
            action.triggered.connect(
                lambda: self._ignore_word(word, occurrence_id, all_occurrences=True)
            )
            scope_actions.append(action)
        if self.action_enabled(LinguisticAction.ADD_TO_DICTIONARY):
            action = QAction(_tr("Add to Dictionary"), menu)
            action.triggered.connect(lambda: self._add_to_dictionary(word))
            scope_actions.append(action)
        if scope_actions:
            menu.addSeparator()
            menu.addActions(scope_actions)
            count += len(scope_actions)
        return count

    def _add_thesaurus_actions(
        self, menu: QMenu, cursor: QTextCursor, word: str
    ) -> int:
        integration = self._integration
        count = 0
        if self.action_enabled(LinguisticAction.SYNONYMS):
            synonyms = integration.service.synonyms(
                word, locale=integration.language
            )
            if synonyms:
                submenu = menu.addMenu(_tr("Synonyms"))
                limit = integration.settings.synonym_limit
                for synonym in synonyms[:limit]:
                    action = submenu.addAction(synonym)
                    action.triggered.connect(
                        lambda _checked=False, value=synonym: (
                            integration.replace_word_at_cursor(
                                value,
                                cursor,
                                expected_word=word,
                            )
                        )
                    )
                if len(synonyms) > limit:
                    submenu.addSeparator()
                    action = submenu.addAction(_tr("More synonyms…"))
                    action.triggered.connect(
                        lambda: self._request_thesaurus(word, cursor, more=True)
                    )
                count += 1
        if self.action_enabled(LinguisticAction.OPEN_THESAURUS):
            action = menu.addAction(_tr("Open Thesaurus…"))
            action.triggered.connect(
                lambda: self._request_thesaurus(word, cursor, more=False)
            )
            count += 1
        return count

    def _add_language_menu(self, menu: QMenu) -> int:
        if not self.action_enabled(LinguisticAction.LANGUAGE):
            return 0
        locales = self._integration.service.available_languages()
        if not locales:
            return 0
        submenu = menu.addMenu(_tr("Language"))
        active = self._integration.language
        for locale in locales:
            info = self._integration.service.dictionary_info(locale)
            availability: list[str] = []
            if info is not None and info.has_spelling:
                availability.append(_tr("Spelling"))
            if info is not None and info.has_thesaurus:
                availability.append(_tr("Thesaurus"))
            capability_text = ", ".join(availability) or _tr("No dictionaries")
            action = submenu.addAction(
                f"{locale_display_name(locale)} [{locale}] — {capability_text}"
            )
            action.setCheckable(True)
            action.setChecked(locale == active)
            action.setData(locale)
            action.triggered.connect(
                lambda _checked=False, value=locale: self._set_language(value)
            )
        if self._integration.language_settings is not None:
            submenu.addSeparator()
            action = submenu.addAction(_tr("Set Current Language as Default"))
            action.triggered.connect(
                lambda _checked=False: self._integration.set_default_language()
            )
        return 1

    def _add_host_provider_actions(self, menu: QMenu, token: object) -> int:
        count = 0
        for provider in self._integration.context_action_providers:
            supplied = provider(self._integration.editor, menu, token)
            if supplied is None:
                continue
            if isinstance(supplied, QAction):
                supplied = (supplied,)
            for action in supplied:
                if not isinstance(action, QAction):
                    raise TypeError("context action providers must return QActions")
                if action not in menu.actions():
                    menu.addAction(action)
                count += 1
        return count

    def _ignore_word(
        self, word: str, occurrence_id: int, *, all_occurrences: bool
    ) -> None:
        integration = self._integration
        document_id = integration.highlighter.document_id
        if all_occurrences:
            changed = integration.service.ignore_for_document(
                word,
                locale=integration.language,
                document_id=document_id,
            )
        else:
            changed = integration.service.ignore_once(
                word,
                locale=integration.language,
                document_id=document_id,
                occurrence_id=occurrence_id,
            )
        if changed:
            integration.invalidate_spelling(word)
            self.word_ignored.emit(word, all_occurrences)

    def _add_to_dictionary(self, word: str) -> None:
        if self._integration.service.add_to_personal_dictionary(
            word, locale=self._integration.language
        ):
            self._integration.invalidate_spelling(word)
            self.word_added_to_dictionary.emit(word)

    def _set_language(self, locale: str) -> None:
        if self._integration.set_language(locale):
            self.language_changed.emit(locale)

    def open_thesaurus_dialog(
        self,
        word: str,
        cursor: QTextCursor,
    ) -> ThesaurusDialog:
        """Open a modeless dialog tied to one stale-safe editor cursor."""
        editor = self._integration.editor
        if editor is None:
            raise RuntimeError("the linguistic integration is detached")
        if not isinstance(cursor, QTextCursor):
            raise TypeError("cursor must be a QTextCursor")
        saved_cursor = QTextCursor(cursor)
        dialog = ThesaurusDialog(
            self._integration.service,
            word,
            replacement_source=word,
            locale=self._integration.language,
            parent=editor,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.replacement_requested.connect(
            lambda expected, replacement: self._integration.replace_word_at_cursor(
                replacement,
                saved_cursor,
                expected_word=expected,
            )
        )
        self._dialogs.add(dialog)
        dialog.destroyed.connect(lambda: self._dialogs.discard(dialog))
        dialog.show()
        return dialog

    def _request_thesaurus(
        self,
        word: str,
        cursor: QTextCursor,
        *,
        more: bool,
    ) -> None:
        if more:
            self.more_synonyms_requested.emit(word)
        else:
            self.open_thesaurus_requested.emit(word)
        self.open_thesaurus_dialog(word, cursor)

    @staticmethod
    def _coerce_action(action: LinguisticAction | str) -> LinguisticAction:
        try:
            return LinguisticAction(action)
        except (TypeError, ValueError) as error:
            raise ValueError(f"unknown linguistic action: {action!r}") from error


__all__ = ["LinguisticAction", "LinguisticContextMenu"]
