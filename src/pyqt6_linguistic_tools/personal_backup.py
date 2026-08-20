"""Portable backup and transactional restore for personal dictionaries."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Iterator, Literal

from pyqt6_linguistic_tools.errors import (
    PersonalDictionaryBackupError,
    PersonalDictionaryError,
)
from pyqt6_linguistic_tools.personal import (
    PersonalDictionary,
    PersonalDictionaryStore,
    _cooperative_file_lock,
    normalize_personal_locale,
    normalize_personal_word,
)


BACKUP_FORMAT = "pyqt6-linguistic-tools.personal-dictionaries"
BACKUP_VERSION = 1
_MAX_BACKUP_BYTES = 32 * 1024 * 1024
_MAX_LOCALES = 1_024
_MAX_WORDS = 1_000_000
RestoreMode = Literal["merge", "replace"]


@dataclass(frozen=True)
class PersonalDictionaryBackupEntry:
    """Validated words for one locale in a backup."""

    locale: str
    words: tuple[str, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)


@dataclass(frozen=True)
class PersonalDictionaryBackupPreview:
    """Complete validated contents suitable for an import preview."""

    path: Path
    version: int
    entries: tuple[PersonalDictionaryBackupEntry, ...]

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(entry.locale for entry in self.entries)

    @property
    def total_words(self) -> int:
        return sum(entry.word_count for entry in self.entries)

    def word_count(self, locale: str) -> int:
        normalized = normalize_personal_locale(locale)
        for entry in self.entries:
            if entry.locale == normalized:
                return entry.word_count
        raise KeyError(normalized)


@dataclass(frozen=True)
class PersonalDictionaryRestoreEntry:
    """Per-locale summary after a successful restore."""

    locale: str
    previous_count: int
    backup_count: int
    final_count: int
    added_count: int


@dataclass(frozen=True)
class PersonalDictionaryRestoreResult:
    """Summary returned only after every selected locale was published."""

    mode: RestoreMode
    entries: tuple[PersonalDictionaryRestoreEntry, ...]

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(entry.locale for entry in self.entries)


class PersonalDictionaryBackupManager:
    """Export and restore one personal-dictionary store without Qt."""

    def __init__(
        self,
        store: PersonalDictionaryStore,
        *,
        lock_timeout: float = 5.0,
        stale_lock_seconds: float = 30.0,
    ) -> None:
        if not isinstance(store, PersonalDictionaryStore):
            raise TypeError("store must be a PersonalDictionaryStore")
        if isinstance(lock_timeout, bool) or not isinstance(lock_timeout, (int, float)):
            raise TypeError("lock_timeout must be a number")
        if isinstance(stale_lock_seconds, bool) or not isinstance(
            stale_lock_seconds, (int, float)
        ):
            raise TypeError("stale_lock_seconds must be a number")
        if lock_timeout < 0 or stale_lock_seconds <= 0:
            raise ValueError("lock timeouts must be non-negative and stale time positive")
        self.store = store
        self._lock_timeout = float(lock_timeout)
        self._stale_lock_seconds = float(stale_lock_seconds)
        self._thread_lock = RLock()

    def inspect(self, source: str | Path) -> PersonalDictionaryBackupPreview:
        """Read and validate a complete backup without changing local data."""
        path = Path(source).expanduser().resolve()
        try:
            size = path.stat().st_size
            if size > _MAX_BACKUP_BYTES:
                raise ValueError("backup exceeds the supported size limit")
            with path.open("r", encoding="utf-8-sig", newline=None) as backup_file:
                payload = json.load(backup_file)
            return self._parse_payload(path, payload)
        except PersonalDictionaryBackupError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise PersonalDictionaryBackupError(
                f"cannot inspect personal dictionary backup: {path}",
                operation="inspect",
                path=path,
            ) from error

    def export(
        self,
        destination: str | Path,
        *,
        locales: Iterable[str] | None = None,
        overwrite: bool = False,
    ) -> PersonalDictionaryBackupPreview:
        """Atomically export selected locales, or every persisted locale."""
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        path = Path(destination).expanduser().resolve()
        if path.is_relative_to(self.store.root):
            raise PersonalDictionaryBackupError(
                "backup destination must be outside the personal dictionary store",
                operation="export",
                path=path,
            )
        selected = self._normalize_locale_selection(locales)
        lock_path = self.store.root / ".personal-dictionaries.lock"
        with self._thread_lock, self._locked_store(lock_path, "export", path):
            if selected is None:
                selected = self.store.available_locales()
            entries = tuple(
                PersonalDictionaryBackupEntry(
                    locale,
                    self.store.for_locale(locale).words(),
                )
                for locale in selected
            )
            payload = self._encode_backup(entries)
            self._publish_export(path, payload, overwrite=overwrite)
        return PersonalDictionaryBackupPreview(path, BACKUP_VERSION, entries)

    def restore(
        self,
        source: str | Path,
        *,
        mode: RestoreMode = "merge",
        locales: Iterable[str] | None = None,
    ) -> PersonalDictionaryRestoreResult:
        """Transactionally restore selected personal dictionaries."""
        if mode not in ("merge", "replace"):
            raise ValueError("mode must be 'merge' or 'replace'")
        preview = self.inspect(source)
        requested = self._normalize_locale_selection(locales)
        by_locale = {entry.locale: entry for entry in preview.entries}
        selected = preview.locales if requested is None else requested
        missing = tuple(locale for locale in selected if locale not in by_locale)
        if missing:
            raise PersonalDictionaryBackupError(
                f"backup does not contain requested locales: {', '.join(missing)}",
                operation="restore",
                path=preview.path,
            )

        root = self.store.root
        lock_path = root / ".personal-dictionaries.lock"
        with self._thread_lock, self._locked_store(
            lock_path, "restore", preview.path
        ):
            return self._restore_locked(preview.path, mode, selected, by_locale)

    @contextmanager
    def _locked_store(
        self, lock_path: Path, operation: str, reported_path: Path
    ) -> Iterator[None]:
        try:
            with _cooperative_file_lock(
                lock_path,
                timeout=self._lock_timeout,
                stale_seconds=self._stale_lock_seconds,
                description="personal dictionary store",
            ):
                yield
        except PersonalDictionaryError as error:
            raise PersonalDictionaryBackupError(
                f"cannot complete personal dictionary {operation}",
                operation=operation,
                path=reported_path,
            ) from error

    def _restore_locked(
        self,
        source: Path,
        mode: RestoreMode,
        selected: tuple[str, ...],
        by_locale: dict[str, PersonalDictionaryBackupEntry],
    ) -> PersonalDictionaryRestoreResult:
        root = self.store.root
        root.mkdir(parents=True, exist_ok=True)
        originals: dict[str, bytes | None] = {}
        staged: dict[str, Path] = {}
        summaries: list[PersonalDictionaryRestoreEntry] = []

        try:
            for locale in selected:
                target = root / f"{locale}.json"
                if target.is_symlink():
                    raise ValueError(f"refusing to replace symbolic link: {target}")
                current = set(PersonalDictionary(locale, root).words())
                backup_words = set(by_locale[locale].words)
                final = current | backup_words if mode == "merge" else backup_words
                originals[locale] = target.read_bytes() if target.exists() else None
                staged[locale] = self._stage_bytes(
                    root,
                    prefix=f".{locale}.restore.",
                    payload=self._encode_personal_dictionary(locale, final),
                )
                summaries.append(
                    PersonalDictionaryRestoreEntry(
                        locale=locale,
                        previous_count=len(current),
                        backup_count=len(backup_words),
                        final_count=len(final),
                        added_count=len(final - current),
                    )
                )
        except (OSError, TypeError, ValueError, PersonalDictionaryError) as error:
            self._cleanup_staged(staged.values())
            raise PersonalDictionaryBackupError(
                f"cannot prepare personal dictionary restore from: {source}",
                operation="restore",
                path=source,
            ) from error

        published: list[str] = []
        try:
            for locale in selected:
                os.replace(staged[locale], root / f"{locale}.json")
                published.append(locale)
        except OSError as error:
            rollback_errors = self._rollback(root, published, originals)
            self._cleanup_staged(staged.values())
            detail = ""
            if rollback_errors:
                detail = "; rollback also failed for " + ", ".join(rollback_errors)
            raise PersonalDictionaryBackupError(
                f"cannot publish personal dictionary restore{detail}",
                operation="restore",
                path=source,
            ) from error
        finally:
            self._cleanup_staged(staged.values())

        return PersonalDictionaryRestoreResult(mode, tuple(summaries))

    def _rollback(
        self,
        root: Path,
        published: list[str],
        originals: dict[str, bytes | None],
    ) -> list[str]:
        failures: list[str] = []
        for locale in reversed(published):
            target = root / f"{locale}.json"
            original = originals[locale]
            try:
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    rollback = self._stage_bytes(
                        root, prefix=f".{locale}.rollback.", payload=original
                    )
                    try:
                        os.replace(rollback, target)
                    finally:
                        rollback.unlink(missing_ok=True)
            except OSError:
                failures.append(locale)
        return failures

    @staticmethod
    def _normalize_locale_selection(
        locales: Iterable[str] | None,
    ) -> tuple[str, ...] | None:
        if locales is None:
            return None
        if isinstance(locales, (str, bytes)):
            raise TypeError("locales must be an iterable of locale strings")
        return tuple(
            sorted(dict.fromkeys(normalize_personal_locale(locale) for locale in locales))
        )

    @staticmethod
    def _parse_payload(path: Path, payload) -> PersonalDictionaryBackupPreview:
        if not isinstance(payload, dict):
            raise ValueError("backup root must be an object")
        if payload.get("format") != BACKUP_FORMAT:
            raise ValueError("unsupported backup format")
        if payload.get("version") != BACKUP_VERSION:
            raise ValueError("unsupported backup version")
        dictionaries = payload.get("dictionaries")
        if not isinstance(dictionaries, list):
            raise ValueError("backup dictionaries must be a list")
        if len(dictionaries) > _MAX_LOCALES:
            raise ValueError("backup contains too many locales")

        entries: list[PersonalDictionaryBackupEntry] = []
        seen_locales: set[str] = set()
        total_words = 0
        for dictionary in dictionaries:
            if not isinstance(dictionary, dict):
                raise ValueError("backup dictionary entry must be an object")
            locale = normalize_personal_locale(dictionary.get("locale"))
            if locale in seen_locales:
                raise ValueError(f"duplicate backup locale: {locale}")
            words = dictionary.get("words")
            if not isinstance(words, list):
                raise ValueError("backup words must be a list")
            normalized_words = tuple(
                sorted(
                    dict.fromkeys(normalize_personal_word(word) for word in words),
                    key=lambda word: (word.casefold(), word),
                )
            )
            total_words += len(normalized_words)
            if total_words > _MAX_WORDS:
                raise ValueError("backup contains too many words")
            entries.append(PersonalDictionaryBackupEntry(locale, normalized_words))
            seen_locales.add(locale)
        entries.sort(key=lambda entry: entry.locale)
        return PersonalDictionaryBackupPreview(path, BACKUP_VERSION, tuple(entries))

    @staticmethod
    def _encode_backup(entries: tuple[PersonalDictionaryBackupEntry, ...]) -> bytes:
        return PersonalDictionaryBackupManager._json_bytes(
            {
                "format": BACKUP_FORMAT,
                "version": BACKUP_VERSION,
                "dictionaries": [
                    {"locale": entry.locale, "words": list(entry.words)}
                    for entry in entries
                ],
            }
        )

    @staticmethod
    def _encode_personal_dictionary(locale: str, words: set[str]) -> bytes:
        return PersonalDictionaryBackupManager._json_bytes(
            {
                "version": 1,
                "locale": locale,
                "words": sorted(words, key=lambda word: (word.casefold(), word)),
            }
        )

    @staticmethod
    def _json_bytes(payload) -> bytes:
        return (
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")

    @staticmethod
    def _stage_bytes(parent: Path, *, prefix: str, payload: bytes) -> Path:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=prefix, suffix=".tmp", dir=parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
        return temporary

    def _publish_export(self, path: Path, payload: bytes, *, overwrite: bool) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._stage_bytes(
                path.parent, prefix=f".{path.name}.", payload=payload
            )
            try:
                if overwrite:
                    os.replace(temporary, path)
                else:
                    os.link(temporary, path)
                    temporary.unlink()
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as error:
            raise PersonalDictionaryBackupError(
                f"cannot export personal dictionary backup: {path}",
                operation="export",
                path=path,
            ) from error

    @staticmethod
    def _cleanup_staged(paths) -> None:
        for path in paths:
            path.unlink(missing_ok=True)


__all__ = [
    "BACKUP_FORMAT",
    "BACKUP_VERSION",
    "PersonalDictionaryBackupEntry",
    "PersonalDictionaryBackupManager",
    "PersonalDictionaryBackupPreview",
    "PersonalDictionaryRestoreEntry",
    "PersonalDictionaryRestoreResult",
    "RestoreMode",
]
