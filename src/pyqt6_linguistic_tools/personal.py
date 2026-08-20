"""Backend-independent personal dictionaries persisted by locale."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
import time
from typing import Iterator
import unicodedata

from pyqt6_linguistic_tools.errors import PersonalDictionaryError
from pyqt6_linguistic_tools.locales import normalize_locale
from pyqt6_linguistic_tools.storage import dictionary_storage_paths


_FORMAT_VERSION = 1


def normalize_personal_word(word: str) -> str:
    """Validate and NFC-normalize one personal spelling word."""
    if not isinstance(word, str):
        raise TypeError("personal dictionary word must be a string")
    normalized = unicodedata.normalize("NFC", word.strip())
    if not normalized:
        raise ValueError("personal dictionary word must not be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError("personal dictionary words cannot contain whitespace")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("personal dictionary words cannot contain control characters")
    return normalized


class PersonalDictionary:
    """A thread-safe and process-cooperative personal dictionary for one locale."""

    def __init__(
        self,
        locale: str,
        root: str | Path | None = None,
        *,
        namespace: str = "pyqt6-linguistic-tools",
        lock_timeout: float = 5.0,
        stale_lock_seconds: float = 30.0,
    ) -> None:
        if isinstance(lock_timeout, bool) or not isinstance(lock_timeout, (int, float)):
            raise TypeError("lock_timeout must be a number")
        if isinstance(stale_lock_seconds, bool) or not isinstance(
            stale_lock_seconds, (int, float)
        ):
            raise TypeError("stale_lock_seconds must be a number")
        if lock_timeout < 0 or stale_lock_seconds <= 0:
            raise ValueError("lock timeouts must be non-negative and stale time positive")
        self.locale = normalize_locale(locale)
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else dictionary_storage_paths(namespace).personal
        )
        self.path = self.root / f"{self.locale}.json"
        self._lock_path = self.root / f".{self.locale}.lock"
        self._lock_timeout = float(lock_timeout)
        self._stale_lock_seconds = float(stale_lock_seconds)
        self._words: set[str] = set()
        self._signature: tuple[int, int] | None = None
        self._loaded = False
        self._revision = 0
        self._thread_lock = RLock()

    @property
    def revision(self) -> int:
        """Increment whenever this instance observes a changed disk snapshot."""
        with self._thread_lock:
            self._refresh_if_changed()
            return self._revision

    def contains(self, word: str, *, case_sensitive: bool = True) -> bool:
        """Return whether *word* is present in the current locale dictionary."""
        normalized = normalize_personal_word(word)
        if not isinstance(case_sensitive, bool):
            raise TypeError("case_sensitive must be a boolean")
        with self._thread_lock:
            self._refresh_if_changed()
            if case_sensitive:
                return normalized in self._words
            folded = normalized.casefold()
            return any(candidate.casefold() == folded for candidate in self._words)

    def words(self) -> tuple[str, ...]:
        """Return a deterministic immutable snapshot."""
        with self._thread_lock:
            self._refresh_if_changed()
            return tuple(sorted(self._words, key=lambda word: (word.casefold(), word)))

    def add_word(self, word: str) -> bool:
        """Persist one word, returning whether the collection changed."""
        return bool(self.add_words((word,)))

    def add_words(self, words: Iterable[str]) -> tuple[str, ...]:
        """Persist multiple words in one locked atomic update."""
        if isinstance(words, (str, bytes)):
            raise TypeError("words must be an iterable of strings, not one string")
        normalized = tuple(dict.fromkeys(normalize_personal_word(word) for word in words))
        if not normalized:
            return ()
        with self._thread_lock, self._file_lock():
            self._load_from_disk()
            added = tuple(word for word in normalized if word not in self._words)
            if added:
                self._words.update(added)
                self._save_atomic()
            return added

    def remove_word(self, word: str) -> bool:
        """Remove one word, returning whether it existed."""
        return bool(self.remove_words((word,)))

    def remove_words(self, words: Iterable[str]) -> tuple[str, ...]:
        """Remove multiple words in one locked atomic update."""
        if isinstance(words, (str, bytes)):
            raise TypeError("words must be an iterable of strings, not one string")
        normalized = tuple(dict.fromkeys(normalize_personal_word(word) for word in words))
        if not normalized:
            return ()
        with self._thread_lock, self._file_lock():
            self._load_from_disk()
            removed = tuple(word for word in normalized if word in self._words)
            if removed:
                self._words.difference_update(removed)
                self._save_atomic()
            return removed

    def clear(self) -> bool:
        """Persist an empty collection, returning whether words were removed."""
        with self._thread_lock, self._file_lock():
            self._load_from_disk()
            if not self._words:
                return False
            self._words.clear()
            self._save_atomic()
            return True

    def reload(self) -> tuple[str, ...]:
        """Force a disk reload and return the new snapshot."""
        with self._thread_lock:
            self._load_from_disk()
            return self.words()

    def _refresh_if_changed(self) -> None:
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            signature = None
        except OSError as error:
            raise PersonalDictionaryError(
                f"cannot inspect personal dictionary: {self.path}", path=self.path
            ) from error
        if not self._loaded or signature != self._signature:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            changed = not self._loaded or bool(self._words) or self._signature is not None
            self._words = set()
            self._signature = None
            self._loaded = True
            if changed:
                self._revision += 1
            return
        try:
            with self.path.open("r", encoding="utf-8-sig") as personal_file:
                payload = json.load(personal_file)
            if not isinstance(payload, dict) or payload.get("version") != _FORMAT_VERSION:
                raise ValueError("unsupported personal dictionary format")
            stored_locale = normalize_locale(payload.get("locale"))
            if stored_locale != self.locale:
                raise ValueError(
                    f"stored locale {stored_locale!r} does not match {self.locale!r}"
                )
            stored_words = payload.get("words")
            if not isinstance(stored_words, list):
                raise ValueError("personal dictionary words must be a list")
            loaded_words = {normalize_personal_word(word) for word in stored_words}
            stat = self.path.stat()
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise PersonalDictionaryError(
                f"cannot load personal dictionary: {self.path}", path=self.path
            ) from error
        signature = (stat.st_mtime_ns, stat.st_size)
        changed = (
            not self._loaded
            or loaded_words != self._words
            or signature != self._signature
        )
        self._words = loaded_words
        self._signature = signature
        self._loaded = True
        if changed:
            self._revision += 1

    def _save_atomic(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.locale}.", suffix=".tmp", dir=self.root
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as output:
                json.dump(
                    {
                        "version": _FORMAT_VERSION,
                        "locale": self.locale,
                        "words": sorted(
                            self._words, key=lambda word: (word.casefold(), word)
                        ),
                    },
                    output,
                    ensure_ascii=False,
                    indent=2,
                )
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            stat = self.path.stat()
            self._signature = (stat.st_mtime_ns, stat.st_size)
            self._loaded = True
            self._revision += 1
        except OSError as error:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            # Restore the last durable snapshot so this instance never claims
            # that a failed mutation was persisted.
            try:
                self._load_from_disk()
            except PersonalDictionaryError:
                pass
            raise PersonalDictionaryError(
                f"cannot save personal dictionary: {self.path}", path=self.path
            ) from error

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._lock_timeout
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(
                    self._lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                try:
                    age = time.time() - self._lock_path.stat().st_mtime
                    if age > self._stale_lock_seconds:
                        self._lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                except OSError as error:
                    raise PersonalDictionaryError(
                        f"cannot inspect personal dictionary lock: {self._lock_path}",
                        path=self._lock_path,
                    ) from error
                if time.monotonic() >= deadline:
                    raise PersonalDictionaryError(
                        f"timed out waiting for personal dictionary lock: {self._lock_path}",
                        path=self._lock_path,
                    )
                time.sleep(0.05)
            except OSError as error:
                raise PersonalDictionaryError(
                    f"cannot lock personal dictionary: {self._lock_path}",
                    path=self._lock_path,
                ) from error
        try:
            os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
            os.close(descriptor)
            descriptor = None
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                self._lock_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise PersonalDictionaryError(
                    f"cannot release personal dictionary lock: {self._lock_path}",
                    path=self._lock_path,
                ) from error


class PersonalDictionaryStore:
    """Create per-locale dictionaries under one application or shared root."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        namespace: str = "pyqt6-linguistic-tools",
    ) -> None:
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else dictionary_storage_paths(namespace).personal
        )

    def for_locale(self, locale: str) -> PersonalDictionary:
        return PersonalDictionary(locale, self.root)

    def available_locales(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        locales = []
        for path in self.root.glob("*.json"):
            try:
                locales.append(normalize_locale(path.stem))
            except (TypeError, ValueError):
                continue
        return tuple(sorted(set(locales)))


__all__ = [
    "PersonalDictionary",
    "PersonalDictionaryStore",
    "normalize_personal_word",
]
