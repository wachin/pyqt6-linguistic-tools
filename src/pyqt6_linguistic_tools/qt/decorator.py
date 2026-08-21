"""Reversible linguistic integration for existing Qt text editors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import weakref

from pyqt6_linguistic_tools.service import LinguisticService
from pyqt6_linguistic_tools.tokenizer import TokenFilter, UnicodeTokenizer
from pyqt6_linguistic_tools.qt._compat import require_pyqt6
from pyqt6_linguistic_tools.qt.settings import QtLinguisticSettings


require_pyqt6()

from PyQt6.QtCore import QObject, Qt, pyqtSignal  # noqa: E402
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

    def __init__(
        self,
        editor: QTextEdit | QPlainTextEdit,
        service: LinguisticService,
        *,
        settings: QtLinguisticSettings | None = None,
        tokenizer: UnicodeTokenizer | None = None,
    ) -> None:
        if not isinstance(service, LinguisticService):
            raise TypeError("service must be a LinguisticService")
        if settings is not None and not isinstance(settings, QtLinguisticSettings):
            raise TypeError("settings must be a QtLinguisticSettings")
        if tokenizer is not None and not isinstance(tokenizer, UnicodeTokenizer):
            raise TypeError("tokenizer must be a UnicodeTokenizer")

        super().__init__()
        self._service = service
        self._settings = settings or QtLinguisticSettings()
        self._base_tokenizer = tokenizer or UnicodeTokenizer()
        self._enabled = True
        self._editor_ref: weakref.ReferenceType[
            QTextEdit | QPlainTextEdit
        ] | None = None
        self._filtered_objects: tuple[QObject, ...] = ()
        self._token_filters: list[TokenFilter] = []
        self._context_action_providers: list[ContextActionProvider] = []
        self.attach(editor)

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
        self.attached_changed.emit(True)
        return True

    def detach(self) -> bool:
        """Remove all installed hooks while leaving the editor unchanged."""
        editor = self.editor
        if editor is None:
            self._clear_attachment()
            return False

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
        self.enabled_changed.emit(enabled)
        return True

    def set_spellcheck_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "spellcheck_enabled", enabled, self.spellcheck_enabled_changed
        )

    def set_highlighting_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "highlighting_enabled", enabled, self.highlighting_enabled_changed
        )

    def set_thesaurus_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "thesaurus_enabled", enabled, self.thesaurus_enabled_changed
        )

    def set_context_menu_enabled(self, enabled: bool) -> bool:
        return self._update_setting(
            "context_menu_enabled", enabled, self.context_menu_enabled_changed
        )

    def add_token_filter(self, token_filter: TokenFilter) -> bool:
        """Register one editor-specific token filter by object identity."""
        if not callable(token_filter):
            raise TypeError("token_filter must be callable")
        if any(current is token_filter for current in self._token_filters):
            return False
        self._token_filters.append(token_filter)
        self.token_filters_changed.emit()
        return True

    def remove_token_filter(self, token_filter: TokenFilter) -> bool:
        for index, current in enumerate(self._token_filters):
            if current is token_filter:
                del self._token_filters[index]
                self.token_filters_changed.emit()
                return True
        return False

    def clear_token_filters(self) -> bool:
        if not self._token_filters:
            return False
        self._token_filters.clear()
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

    def eventFilter(self, watched: QObject, event: object) -> bool:  # noqa: N802
        """Observe editor events without consuming or changing host behavior."""
        return False

    def _update_setting(self, name: str, enabled: bool, signal: object) -> bool:
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
    def _validate_editor(editor: object) -> None:
        if not isinstance(editor, (QTextEdit, QPlainTextEdit)):
            raise TypeError("editor must be a QTextEdit or QPlainTextEdit")

    def _on_editor_destroyed(self, _editor: QObject | None = None) -> None:
        self._clear_attachment()
        self.attached_changed.emit(False)

    def _clear_attachment(self) -> None:
        self._editor_ref = None
        self._filtered_objects = ()


__all__ = ["ContextActionProvider", "LinguisticTextEditDecorator"]
