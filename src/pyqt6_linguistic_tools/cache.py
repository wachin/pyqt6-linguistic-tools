"""Thread-safe bounded cache for loaded linguistic backends."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

from pyqt6_linguistic_tools.backends.base import LinguisticBackend


Key = TypeVar("Key", bound=Hashable)
Backend = TypeVar("Backend", bound=LinguisticBackend)
Value = TypeVar("Value")


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Immutable bounded-cache counters and current occupancy."""

    hits: int
    misses: int
    evictions: int
    size: int
    max_size: int


@dataclass(frozen=True, slots=True)
class LinguisticResultCacheStats:
    """Statistics for the three service result caches."""

    spelling: CacheStats
    suggestions: CacheStats
    thesaurus: CacheStats


class ResultCache(Generic[Key, Value]):
    """Thread-safe bounded LRU cache which supports cached ``None`` values."""

    def __init__(self, max_size: int = 2048) -> None:
        if isinstance(max_size, bool) or not isinstance(max_size, int):
            raise TypeError("max_size must be an integer")
        if max_size < 1:
            raise ValueError("max_size must be at least one")
        self._max_size = max_size
        self._items: OrderedDict[Key, Value] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = RLock()

    @property
    def max_size(self) -> int:
        return self._max_size

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def keys(self) -> tuple[Key, ...]:
        """Return keys from least to most recently used."""
        with self._lock:
            return tuple(self._items)

    def try_get(self, key: Key) -> tuple[bool, Value | None]:
        """Return ``(found, value)`` while retaining cached ``None`` distinctly."""
        with self._lock:
            try:
                value = self._items.pop(key)
            except KeyError:
                self._misses += 1
                return False, None
            self._items[key] = value
            self._hits += 1
            return True, value

    def put(self, key: Key, value: Value) -> None:
        """Insert or refresh one value and evict the least-recently-used key."""
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = value
            while len(self._items) > self._max_size:
                self._items.popitem(last=False)
                self._evictions += 1

    def invalidate(self, predicate: Callable[[Key], bool]) -> int:
        """Remove matching keys and return the number invalidated."""
        if not callable(predicate):
            raise TypeError("predicate must be callable")
        with self._lock:
            keys = tuple(key for key in self._items if predicate(key))
            for key in keys:
                del self._items[key]
            return len(keys)

    def clear(self, *, reset_stats: bool = False) -> int:
        """Remove all values, optionally resetting counters, and return the count."""
        if not isinstance(reset_stats, bool):
            raise TypeError("reset_stats must be a boolean")
        with self._lock:
            removed = len(self._items)
            self._items.clear()
            if reset_stats:
                self._hits = 0
                self._misses = 0
                self._evictions = 0
            return removed

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._items),
                max_size=self._max_size,
            )


class BackendCache(Generic[Key, Backend]):
    """An LRU cache which unloads engines on eviction and clearing.

    Factories should create lazy backend instances. Retrieving an entry does
    not load its dictionary; the first linguistic operation does.
    """

    def __init__(self, max_size: int = 2) -> None:
        if isinstance(max_size, bool) or not isinstance(max_size, int):
            raise TypeError("max_size must be an integer")
        if max_size < 1:
            raise ValueError("max_size must be at least one")
        self._max_size = max_size
        self._items: OrderedDict[Key, Backend] = OrderedDict()
        self._lock = RLock()

    @property
    def max_size(self) -> int:
        return self._max_size

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def keys(self) -> tuple[Key, ...]:
        """Return keys from least to most recently used."""
        with self._lock:
            return tuple(self._items)

    def get_or_create(self, key: Key, factory: Callable[[], Backend]) -> Backend:
        """Return *key*, or create it lazily and evict the oldest entry."""
        with self._lock:
            try:
                backend = self._items.pop(key)
            except KeyError:
                backend = factory()
            self._items[key] = backend
            while len(self._items) > self._max_size:
                _, evicted = self._items.popitem(last=False)
                evicted.unload()
            return backend

    def remove(self, key: Key) -> bool:
        """Unload and remove *key*, returning whether it existed."""
        with self._lock:
            backend = self._items.pop(key, None)
            if backend is None:
                return False
            backend.unload()
            return True

    def clear(self) -> None:
        """Unload and remove every cached backend."""
        with self._lock:
            backends = tuple(self._items.values())
            self._items.clear()
            for backend in backends:
                backend.unload()

    def __iter__(self) -> Iterator[Key]:
        return iter(self.keys())
