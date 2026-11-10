"""Optional PyQt6 integration boundary for the widget-independent core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyqt6_linguistic_tools.qt._compat import (
    QtIntegrationUnavailableError,
    QtRuntimeInfo,
    pyqt6_available,
    qt_runtime_info,
    require_pyqt6,
)
from pyqt6_linguistic_tools.qt.settings import QtLinguisticSettings

if TYPE_CHECKING:
    from pyqt6_linguistic_tools.qt.async_spellcheck import AsyncSpellCheckController
    from pyqt6_linguistic_tools.qt.language_settings import QtLanguageSettingsStore
    from pyqt6_linguistic_tools.qt.context_menu import (
        LinguisticAction,
        LinguisticContextMenu,
    )
    from pyqt6_linguistic_tools.qt.decorator import (
        ContextActionProvider,
        LinguisticTextEditDecorator,
    )
    from pyqt6_linguistic_tools.qt.dictionary_manager import (
        DictionaryDownloadManagerDialog,
        DictionaryDownloadManagerWidget,
        DictionaryManagerDialog,
        DictionaryManagerWidget,
    )
    from pyqt6_linguistic_tools.qt.i18n import (
        install_toolkit_translations,
        installed_toolkit_translator,
        translation_candidates,
        uninstall_toolkit_translations,
    )
    from pyqt6_linguistic_tools.qt.spell_highlighter import (
        SpellCheckHighlighter,
        default_misspelling_format,
    )
    from pyqt6_linguistic_tools.qt.thesaurus_dialog import (
        ThesaurusDialog,
        preserve_simple_capitalization,
    )


__all__ = [
    "AsyncSpellCheckController",
    "ContextActionProvider",
    "DictionaryDownloadManagerDialog",
    "DictionaryDownloadManagerWidget",
    "DictionaryManagerDialog",
    "DictionaryManagerWidget",
    "LinguisticTextEditDecorator",
    "LinguisticAction",
    "LinguisticContextMenu",
    "SpellCheckHighlighter",
    "ThesaurusDialog",
    "QtIntegrationUnavailableError",
    "QtLanguageSettingsStore",
    "QtLinguisticSettings",
    "QtRuntimeInfo",
    "default_misspelling_format",
    "install_toolkit_translations",
    "installed_toolkit_translator",
    "preserve_simple_capitalization",
    "pyqt6_available",
    "qt_runtime_info",
    "require_pyqt6",
    "translation_candidates",
    "uninstall_toolkit_translations",
]


def __getattr__(name: str) -> object:
    """Load widget classes only when applications explicitly request them."""
    if name in {"ContextActionProvider", "LinguisticTextEditDecorator"}:
        from pyqt6_linguistic_tools.qt import decorator

        return getattr(decorator, name)
    if name in {
        "DictionaryDownloadManagerDialog",
        "DictionaryDownloadManagerWidget",
        "DictionaryManagerDialog",
        "DictionaryManagerWidget",
    }:
        from pyqt6_linguistic_tools.qt import dictionary_manager

        return getattr(dictionary_manager, name)
    if name in {
        "install_toolkit_translations",
        "installed_toolkit_translator",
        "translation_candidates",
        "uninstall_toolkit_translations",
    }:
        from pyqt6_linguistic_tools.qt import i18n

        return getattr(i18n, name)
    if name in {"SpellCheckHighlighter", "default_misspelling_format"}:
        from pyqt6_linguistic_tools.qt import spell_highlighter

        return getattr(spell_highlighter, name)
    if name == "AsyncSpellCheckController":
        from pyqt6_linguistic_tools.qt import async_spellcheck

        return async_spellcheck.AsyncSpellCheckController
    if name == "QtLanguageSettingsStore":
        from pyqt6_linguistic_tools.qt import language_settings

        return language_settings.QtLanguageSettingsStore
    if name in {"LinguisticAction", "LinguisticContextMenu"}:
        from pyqt6_linguistic_tools.qt import context_menu

        return getattr(context_menu, name)
    if name in {"ThesaurusDialog", "preserve_simple_capitalization"}:
        from pyqt6_linguistic_tools.qt import thesaurus_dialog

        return getattr(thesaurus_dialog, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
