from __future__ import annotations

import pytest

from pyqt6_linguistic_tools import ResultCache


def test_result_cache_distinguishes_cached_none_and_updates_lru_order():
    cache: ResultCache[str, object | None] = ResultCache(max_size=2)
    cache.put("none", None)
    cache.put("value", "result")

    assert cache.try_get("none") == (True, None)
    cache.put("new", 3)

    assert cache.keys() == ("none", "new")
    assert cache.try_get("value") == (False, None)
    stats = cache.stats()
    assert (stats.hits, stats.misses, stats.evictions) == (1, 1, 1)
    assert (stats.size, stats.max_size) == (2, 2)


def test_result_cache_invalidation_clear_and_stats_reset():
    cache: ResultCache[tuple[str, str], bool] = ResultCache(max_size=4)
    cache.put(("es_EC", "hola"), True)
    cache.put(("en_US", "hello"), True)
    cache.try_get(("es_EC", "missing"))

    assert cache.invalidate(lambda key: key[0] == "es_EC") == 1
    assert cache.keys() == (("en_US", "hello"),)
    assert cache.clear() == 1
    assert cache.stats().misses == 1
    assert cache.clear(reset_stats=True) == 0
    assert cache.stats().misses == 0


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_result_cache_rejects_invalid_bounds(value):
    with pytest.raises((TypeError, ValueError)):
        ResultCache(max_size=value)


def test_result_cache_validates_predicate_and_reset_flag():
    cache = ResultCache(max_size=1)

    with pytest.raises(TypeError):
        cache.invalidate(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cache.clear(reset_stats=1)  # type: ignore[arg-type]
