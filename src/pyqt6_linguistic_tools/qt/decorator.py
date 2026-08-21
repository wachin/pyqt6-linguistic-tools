"""Reversible linguistic integration for existing Qt text editors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import unicodedata
import weakref

from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.tokenizer import (
    TokenFilter,
    UnicodeTokenizer,
    WordToken,
)
from pyqt6_linguistic_tools.qt._compat import require_pyqt6
from pyqt6_linguistic_tools.qt.async_spellcheck import AsyncSpellCheckController
from pyqt6_linguistic_tools.qt.context_menu import LinguisticContextMenu
from pyqt6_linguistic_tools.qt.language_settings import QtLanguageSettingsStore
from pyqt6_linguistic_tools.qt.settings import QtLinguisticSettings
from pyqt6_linguistic_tools.qt.spell_highlighter import SpellCheckHighlighter


require_pyqt6()

from PyQt6.QtCore import QObject, Qt, pyqtBoundSignal, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QTextCursor  # noqa: E402
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit  # noqa: E402


ContextActionProvider = Callable[..., object]
"""Callback retained for the non-destructive context-menu integration."""


class LinguisticTextEditDecorator(QObject):
    """Attach per-editor linguistic state without subclassing the editor.

    The host owns the editor and the linguistic service. The decorator is a
    child of the editor while attached, follows its lifetime, and never changes
    the service-wide enable flags. This allows several editors to share one
    service while retaining independent user-interface settings.
    """

    attached_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)
    spellcheck_enabled_changed = pyqtSignal(bool)
    highlighting_enabled_changed = pyqtSignal(bool)
    thesaurus_enabled_changed = pyqtSignal(bool)
    context_menu_enabled_changed = pyqtSignal(bool)
    token_filters_changed = pyqtSignal()
    context_action_providers_changed = pyqtSignal()
    language_changed = pyqtSignal(str)

    def __init__(
        self,
        editor: QTextEdit | QPlainTextEdit,
        service: LinguisticService,
        *,
        settings: QtLinguisticSettings | None = None,
        tokenizer: UnicodeTokenizer | None = None,
        language: str | None = None,
        language_settings: QtLanguageSettingsStore | None = None,
        document_key: str | None = None,
    ) -> None:
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if settings is not None and not isinstance(settings, QtLinguisticSettings):
            raise TypeError("settings must be a QtLinguisticSettings")
        if tokenizer is not None and not isinstance(tokenizer, UnicodeTokenizer):
            raise TypeError("tokenizer must be a UnicodeTokenizer")
        if language_settings is not None and not isinstance(
            language_settings, QtLanguageSettingsStore
        ):
            raise TypeError("language_settings must be a QtLanguageSettingsStore")
        if document_key is not None and (
            not isinstance(document_key, str) or not document_key.strip()
        ):
            raise ValueError("document_key must be a non-empty string or None")

        super().__init__()
        self._service = service
        self._settings = settings or QtLinguisticSettings()
        self._base_tokenizer = tokenizer or UnicodeTokenizer()
        self._language_settings = language_settings
        self._document_key = (
            document_key.strip() if document_key is not None else None
        )
        stored_language = None
        if language_settings is not None:
            if self._document_key is not None:
                stored_language = language_settings.document_language(
                    self._document_key
                )
            if stored_language is None:
                stored_language = language_settings.default_language()
        self._language = normalize_locale(
            language or stored_language or service.language
        )
        self._enabled = True
        self._editor_ref: weakref.ReferenceType[
            QTextEdit | QPlainTextEdit
        ] | None = None
        self._filtered_objects: tuple[QObject, ...] = ()
        self._token_filters: list[TokenFilter] = []
        self._context_action_providers: list[ContextActionProvider] = []
        self._highlighter: SpellCheckHighlighter | None = None
        self._async_controller: AsyncSpellCheckController | None = None
        self._context_menu: LinguisticContextMenu | None = None
        self.attach(editor)
        document = editor.document()
        if document is None:
            raise RuntimeError("the editor did not provide a text document")
        self._highlighter = SpellCheckHighlighter(
            document,
            service,
            tokenizer=self.create_tokenizer(),
            language=self._language,
            enabled=self.highlighting_active,
            check_on_cache_miss=False,
            parent=self,
        )
        self._async_controller = AsyncSpellCheckController(
            self._highlighter,
            service,
            debounce_ms=self._settings.debounce_ms,
            parent=self,
        )
        self._async_controller.set_document(document)
        self._async_controller.set_lifetime_guard(editor)
        self._context_menu = LinguisticContextMenu(self, parent=self)
        self._highlighter.rehighlight()

    @property
    def service(self) -> LinguisticService:
        """Return the shared core service; ownership remains with the host."""
        return self._service

    @property
    def editor(self) -> QTextEdit | QPlainTextEdit | None:
        """Return the attached editor, or ``None`` after detaching/destruction."""
        if self._editor_ref is None:
            return None
        editor = self._editor_ref()
        if editor is None:
            return None
        try:
            editor.thread()
        except RuntimeError:
            return None
        return editor

    @property
    def is_attached(self) -> bool:
        return self.editor is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def settings(self) -> QtLinguisticSettings:
        return self._settings

    @property
    def language(self) -> str:
        """Return this editor's language, independent of other editors."""
        return self._language

    @property
    def language_settings(self) -> QtLanguageSettingsStore | None:
        return self._language_settings

    @property
    def document_key(self) -> str | None:
        return self._document_key

    @property
    def spellcheck_enabled(self) -> bool:
        return self._settings.spellcheck_enabled

    @property
    def spellcheck_active(self) -> bool:
        return self._enabled and self.spellcheck_enabled

    @property
    def highlighting_enabled(self) -> bool:
        return self._settings.highlighting_enabled

    @property
    def highlighting_active(self) -> bool:
        return self.spellcheck_active and self.highlighting_enabled

    @property
    def thesaurus_enabled(self) -> bool:
        return self._settings.thesaurus_enabled

    @property
    def thesaurus_active(self) -> bool:
        return self._enabled and self.thesaurus_enabled

    @property
    def context_menu_enabled(self) -> bool:
        return self._settings.context_menu_enabled

    @property
    def context_menu_active(self) -> bool:
        return self._enabled and self.context_menu_enabled

    @property
    def token_filters(self) -> tuple[TokenFilter, ...]:
        return tuple(self._token_filters)

    @property
    def context_action_providers(self) -> tuple[ContextActionProvider, ...]:
        return tuple(self._context_action_providers)

    @property
    def highlighter(self) -> SpellCheckHighlighter:
        """Return the decorator-owned spelling highlighter."""
        if self._highlighter is None:
            raise RuntimeError("the highlighter has not been initialized")
        return self._highlighter

    @property
    def async_controller(self) -> AsyncSpellCheckController:
        """Return the decorator-owned debounced spelling controller."""
        if self._async_controller is None:
            raise RuntimeError("the asynchronous controller has not been initialized")
        return self._async_controller

    @property
    def context_menu(self) -> LinguisticContextMenu:
        """Return the decorator-owned additive context-menu component."""
        if self._context_menu is None:
            raise RuntimeError("the context menu has not been initialized")
        return self._context_menu

    def attach(self, editor: QTextEdit | QPlainTextEdit) -> bool:
        """Attach to an existing supported editor and return whether it changed."""
        self._validate_editor(editor)
        current = self.editor
        if current is editor:
            return False
        if current is not None:
            raise RuntimeError("detach the current editor before attaching another")

        direct_children = editor.findChildren(
            LinguisticTextEditDecorator,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        if any(child is not self and child.is_attached for child in direct_children):
            raise RuntimeError("the editor already has a linguistic decorator")

        self.setParent(editor)
        self._editor_ref = weakref.ref(editor)
        objects: list[QObject] = [editor]
        viewport = editor.viewport()
        if viewport is not None:
            objects.append(viewport)
        for watched in objects:
            watched.installEventFilter(self)
        self._filtered_objects = tuple(objects)
        editor.destroyed.connect(self._on_editor_destroyed)
        if self._highlighter is not None:
            self._highlighter.set_document_id(id(editor.document()))
            self._highlighter.setDocument(editor.document())
            if self._async_controller is not None:
                self._async_controller.set_document(editor.document())
                self._async_controller.set_lifetime_guard(editor)
            self._sync_highlighter_enabled()
            self._highlighter.rehighlight()
        self.attached_changed.emit(True)
        return True

    def detach(self) -> bool:
        """Remove all installed hooks while leaving the editor unchanged."""
        editor = self.editor
        if editor is None:
            self._clear_attachment()
            return False

        if self._highlighter is not None:
            if self._async_controller is not None:
                self._async_controller.set_document(None)
                self._async_controller.set_lifetime_guard(None)
            self._highlighter.setDocument(None)

        for watched in self._filtered_objects:
            try:
                watched.removeEventFilter(self)
            except RuntimeError:
                pass
        try:
            editor.destroyed.disconnect(self._on_editor_destroyed)
        except (RuntimeError, TypeError):
            pass
        self._clear_attachment()
        if self.parent() is editor:
            self.setParent(None)
        self.attached_changed.emit(False)
        return True

    def set_enabled(self, enabled: bool) -> bool:
        """Enable or disable all decorator features without losing preferences."""
        enabled = self._validate_boolean(enabled)
        if enabled == self._enabled:
            return False
        self._enabled = enabled
        self._sync_highlighter_enabled()
        self.enabled_changed.emit(enabled)
        return True

    def set_spellcheck_enabled(self, enabled: bool) -> bool:
        changed = self._update_setting(
            "spellcheck_enabled", enabled, self.spellcheck_enabled_changed
        )
        if changed:
            self._sync_highlighter_enabled()
        return changed

    def set_highlighting_enabled(self, enabled: bool) -> bool:
        changed = self._update_setting(
            "highlighting_enabled", enabled, self.highlighting_enabled_changed
        )
        if changed:
            self._sync_highlighter_enabled()
        return changed

    def set_thesaurus_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "thesaurus_enabled", enabled, self.thesaurus_enabled_changed
        )

    def set_context_menu_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "context_menu_enabled", enabled, self.context_menu_enabled_changed
        )

    def set_language(self, language: str, *, persist: bool = True) -> bool:
        """Change only this editor's locale and refresh its linguistic state."""
        if not isinstance(persist, bool):
            raise TypeError("persist must be a boolean")
        language = normalize_locale(language)
        if language == self._language:
            return False
        self.async_controller.cancel(clear_pending=True)
        self._language = language
        self._service.personal_dictionary(language)
        self.highlighter.set_language(language)
        if (
            persist
            and self._language_settings is not None
            and self._document_key is not None
        ):
            self._language_settings.set_document_language(
                self._document_key, language
            )
        self.language_changed.emit(language)
        return True

    def set_default_language(self, language: str | None = None) -> bool:
        """Persist a toolkit default through the host-provided QSettings store."""
        if self._language_settings is None:
            raise RuntimeError("no language settings store is configured")
        return self._language_settings.set_default_language(
            language or self._language
        )

    def add_token_filter(self, token_filter: TokenFilter) -> bool:
        """Register one editor-specific token filter by object identity."""
        if not callable(token_filter):
            raise TypeError("token_filter must be callable")
        if any(current is token_filter for current in self._token_filters):
            return False
        self._token_filters.append(token_filter)
        self._sync_highlighter_tokenizer()
        self.token_filters_changed.emit()
        return True

    def remove_token_filter(self, token_filter: TokenFilter) -> bool:
        for index, current in enumerate(self._token_filters):
            if current is token_filter:
                del self._token_filters[index]
                self._sync_highlighter_tokenizer()
                self.token_filters_changed.emit()
                return True
        return False

    def clear_token_filters(self) -> bool:
        if not self._token_filters:
            return False
        self._token_filters.clear()
        self._sync_highlighter_tokenizer()
        self.token_filters_changed.emit()
        return True

    def create_tokenizer(self) -> UnicodeTokenizer:
        """Compose base and editor-specific filters for future highlighters."""
        return UnicodeTokenizer(
            self._base_tokenizer.config,
            token_filters=(
                *self._base_tokenizer.token_filters,
                *self._token_filters,
            ),
        )

    def word_at_cursor(self, cursor: QTextCursor | None = None) -> WordToken | None:
        """Return the retained word at a Qt cursor using exact UTF-16 offsets.

        A cursor immediately after a word still refers to that word, matching
        normal text-editor behavior while typing. Punctuation and whitespace do
        not inherit the preceding word.
        """
        editor = self.editor
        if editor is None:
            return None
        if cursor is None:
            cursor = editor.textCursor()
        elif not isinstance(cursor, QTextCursor):
            raise TypeError("cursor must be a QTextCursor or None")
        if cursor.isNull() or cursor.document() is not editor.document():
            raise ValueError("cursor must belong to the attached editor document")

        block = cursor.block()
        if not block.isValid():
            return None
        position_in_block = cursor.positionInBlock()
        block_position = block.position()
        for local_token in self.create_tokenizer().iter_tokens(block.text()):
            if local_token.utf16_start <= position_in_block < local_token.utf16_end:
                return self._document_token(local_token, block_position)
            if position_in_block == local_token.utf16_end:
                return self._document_token(local_token, block_position)
            if local_token.utf16_start > position_in_block:
                break
        return None

    def cursor_for_word(self, token: WordToken) -> QTextCursor | None:
        """Create a selecting cursor, or return ``None`` for a stale token."""
        if not isinstance(token, WordToken):
            raise TypeError("token must be a WordToken")
        editor = self.editor
        if editor is None:
            return None
        cursor = QTextCursor(editor.document())
        cursor.setPosition(token.utf16_start)
        cursor.setPosition(
            token.utf16_end,
            QTextCursor.MoveMode.KeepAnchor,
        )
        if cursor.selectedText() != token.text:
            return None
        return cursor

    def check_word_at_cursor(self, cursor: QTextCursor | None = None) -> bool | None:
        """Check the current word, or return ``None`` when checking is inactive."""
        if not self.spellcheck_active:
            return None
        token = self.word_at_cursor(cursor)
        if token is None:
            return None
        return self._service.check_word(token.normalized, locale=self._language)

    def suggestions_at_cursor(
        self,
        cursor: QTextCursor | None = None,
        *,
        limit: int | None = None,
    ) -> tuple[str, ...]:
        """Return bounded suggestions for the current retained word."""
        if not self.spellcheck_active:
            return ()
        token = self.word_at_cursor(cursor)
        if token is None:
            return ()
        effective_limit = self._settings.suggestion_limit if limit is None else limit
        return self._service.suggestions(
            token.normalized,
            locale=self._language,
            limit=effective_limit,
        )

    def replace_word_at_cursor(
        self,
        replacement: str,
        cursor: QTextCursor | None = None,
        *,
        expected_word: str | None = None,
    ) -> bool:
        """Replace exactly the current token and reject stale asynchronous data."""
        replacement = self._validate_replacement(replacement)
        if expected_word is not None and not isinstance(expected_word, str):
            raise TypeError("expected_word must be a string or None")
        editor = self.editor
        if editor is None or editor.isReadOnly():
            return False
        token = self.word_at_cursor(cursor)
        if token is None:
            return False
        if expected_word is not None and token.normalized != unicodedata.normalize(
            "NFC", expected_word
        ):
            return False
        replacement_cursor = self.cursor_for_word(token)
        if replacement_cursor is None:
            return False

        replacement_cursor.beginEditBlock()
        replacement_cursor.insertText(replacement)
        replacement_cursor.endEditBlock()
        editor.setTextCursor(replacement_cursor)
        return True

    def invalidate_spelling(self, word: str | None = None) -> int:
        """Refresh highlighting after personal or ignored-word state changes."""
        if word is None:
            return self.highlighter.clear_cache()
        return self.highlighter.invalidate_word(word)

    def add_context_action_provider(self, provider: ContextActionProvider) -> bool:
        """Retain a host callback for the future additive context menu."""
        if not callable(provider):
            raise TypeError("provider must be callable")
        if any(current is provider for current in self._context_action_providers):
            return False
        self._context_action_providers.append(provider)
        self.context_action_providers_changed.emit()
        return True

    def remove_context_action_provider(self, provider: ContextActionProvider) -> bool:
        for index, current in enumerate(self._context_action_providers):
            if current is provider:
                del self._context_action_providers[index]
                self.context_action_providers_changed.emit()
                return True
        return False

    def clear_context_action_providers(self) -> bool:
        if not self._context_action_providers:
            return False
        self._context_action_providers.clear()
        self.context_action_providers_changed.emit()
        return True

    def eventFilter(  # noqa: N802
        self, watched: QObject | None, event: object
    ) -> bool:
        """Observe editor events without consuming or changing host behavior."""
        if watched is None:
            return False
        context_menu = getattr(self, "_context_menu", None)
        if context_menu is not None and context_menu.handle_event(watched, event):
            return True
        return False

    def _update_setting(
        self, name: str, enabled: bool, signal: pyqtBoundSignal
    ) -> bool:
        enabled = self._validate_boolean(enabled)
        if getattr(self._settings, name) == enabled:
            return False
        self._settings = replace(self._settings, **{name: enabled})
        signal.emit(enabled)
        return True

    @staticmethod
    def _validate_boolean(enabled: bool) -> bool:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")
        return enabled

    @staticmethod
    def _validate_replacement(replacement: str) -> str:
        if not isinstance(replacement, str):
            raise TypeError("replacement must be a string")
        if not replacement:
            raise ValueError("replacement must not be empty")
        if any(character in replacement for character in ("\x00", "\r", "\n")):
            raise ValueError("replacement must be a single line without NUL")
        return replacement

    @staticmethod
    def _document_token(token: WordToken, block_position: int) -> WordToken:
        """Keep Python offsets block-local and make Qt offsets document-global."""
        return WordToken(
            text=token.text,
            start=token.start,
            end=token.end,
            utf16_start=block_position + token.utf16_start,
            utf16_end=block_position + token.utf16_end,
        )

    @staticmethod
    def _validate_editor(editor: object) -> None:
        if not isinstance(editor, (QTextEdit, QPlainTextEdit)):
            raise TypeError("editor must be a QTextEdit or QPlainTextEdit")

    def _on_editor_destroyed(self, _editor: QObject | None = None) -> None:
        if self._async_controller is not None:
            self._async_controller.set_document(None)
            self._async_controller.set_lifetime_guard(None)
        self._clear_attachment()
        self.attached_changed.emit(False)

    def _sync_highlighter_enabled(self) -> None:
        if self._highlighter is not None:
            self._highlighter.set_enabled(self.highlighting_active)
        if self._async_controller is not None:
            self._async_controller.set_enabled(self.highlighting_active)

    def _sync_highlighter_tokenizer(self) -> None:
        if self._highlighter is not None:
            self._highlighter.set_tokenizer(self.create_tokenizer())

    def _clear_attachment(self) -> None:
        self._editor_ref = None
        self._filtered_objects = ()


__all__ = ["ContextActionProvider", "LinguisticTextEditDecorator"]
