"""QSettings persistence for default and per-document languages."""

from __future__ import annotations

from urllib.parse import quote

from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()

from PyQt6.QtCore import QSettings  # noqa: E402


class QtLanguageSettingsStore:
    """Persist language choices without imposing an application settings file."""

    def __init__(self, settings: QSettings, *, group: str = "linguistic") -> None:
        if not isinstance(settings, QSettings):
            raise TypeError("settings must be a QSettings")
        if not isinstance(group, str):
            raise TypeError("group must be a string")
        group = group.strip().strip("/")
        if not group:
            raise ValueError("group must not be empty")
        self._settings = settings
        self._group = group

    @property
    def settings(self) -> QSettings:
        return self._settings

    @property
    def group(self) -> str:
        return self._group

    def default_language(self, fallback: str | None = None) -> str | None:
        return self._read("default_language", fallback)

    def set_default_language(self, locale: str) -> bool:
        return self._write("default_language", locale)

    def document_language(
        self, document_key: str, fallback: str | None = None
    ) -> str | None:
        return self._read(self._document_path(document_key), fallback)

    def set_document_language(self, document_key: str, locale: str) -> bool:
        return self._write(self._document_path(document_key), locale)

    def clear_document_language(self, document_key: str) -> bool:
        path = self._path(self._document_path(document_key))
        existed = self._settings.contains(path)
        if existed:
            self._settings.remove(path)
            self._settings.sync()
        return existed

    def _read(self, key: str, fallback: str | None) -> str | None:
        value = self._settings.value(self._path(key), None)
        if isinstance(value, str) and value.strip():
            try:
                return normalize_locale(value)
            except ValueError:
                pass
        return None if fallback is None else normalize_locale(fallback)

    def _write(self, key: str, locale: str) -> bool:
        locale = normalize_locale(locale)
        path = self._path(key)
        if self._settings.value(path, None) == locale:
            return False
        self._settings.setValue(path, locale)
        self._settings.sync()
        return True

    def _path(self, key: str) -> str:
        return f"{self._group}/{key}"

    @staticmethod
    def _document_path(document_key: str) -> str:
        if not isinstance(document_key, str):
            raise TypeError("document_key must be a string")
        document_key = document_key.strip()
        if not document_key:
            raise ValueError("document_key must not be empty")
        return f"documents/{quote(document_key, safe='')}/language"


__all__ = ["QtLanguageSettingsStore"]
