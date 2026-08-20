"""Thread-safe bounded cache for loaded linguistic backends."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from threading import RLock
from typing import Generic, TypeVar

from pyqt6_linguistic_tools.backends.base import LinguisticBackend


Key = TypeVar("Key", bound=Hashable)
Backend = TypeVar("Backend", bound=LinguisticBackend)


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

