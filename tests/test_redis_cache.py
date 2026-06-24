"""Tests for RedisCache using a minimal in-process fake."""

from __future__ import annotations

import json
from time import time

import pytest

from tonflow.cache import RedisCache


class FakeRedis:
    """Minimal synchronous Redis fake — only the methods RedisCache uses."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, float | None]] = {}

    def get(self, key: str) -> bytes | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at <= time():
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str | bytes, *, px: int | None = None) -> None:
        expires_at = (time() + px / 1000) if px is not None else None
        raw = value.encode() if isinstance(value, str) else value
        self._store[key] = (raw, expires_at)

    def delete(self, *keys: str | bytes) -> None:
        for key in keys:
            k = key.decode() if isinstance(key, bytes) else key
            self._store.pop(k, None)

    def scan(self, cursor: int, *, match: str, count: int) -> tuple[int, list[bytes]]:
        import fnmatch

        matched = [k.encode() for k in self._store if fnmatch.fnmatch(k, match)]
        return 0, matched


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache(prefix: str = "tonflow:") -> tuple[RedisCache, FakeRedis]:
    redis = FakeRedis()
    cache = RedisCache(redis, prefix=prefix)
    return cache, redis


# ---------------------------------------------------------------------------
# Basic get / set
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing_key() -> None:
    cache, _ = _make_cache()
    assert cache.get("missing") is None


def test_set_and_get_roundtrip() -> None:
    cache, _ = _make_cache()
    payload = {"transactions": [{"hash": "abc", "lt": 1}]}
    cache.set("key1", payload)
    assert cache.get("key1") == payload


def test_set_uses_prefix_in_redis_key() -> None:
    cache, redis = _make_cache(prefix="myapp:")
    cache.set("txs:EQ123:20:None", {"items": []})
    stored_keys = list(redis._store.keys())
    assert stored_keys == ["myapp:txs:EQ123:20:None"]


def test_get_returns_none_after_ttl_expires() -> None:
    cache, redis = _make_cache()
    cache.set("expired", {"x": 1}, ttl_seconds=0.001)
    import time

    time.sleep(0.01)
    assert cache.get("expired") is None


def test_get_returns_value_within_ttl() -> None:
    cache, _ = _make_cache()
    cache.set("fresh", {"x": 2}, ttl_seconds=60)
    assert cache.get("fresh") == {"x": 2}


def test_set_without_ttl_does_not_expire() -> None:
    cache, redis = _make_cache()
    cache.set("permanent", {"y": 3})
    _, expires_at = redis._store["tonflow:permanent"]
    assert expires_at is None


def test_set_with_ttl_stores_px_in_milliseconds() -> None:
    cache, redis = _make_cache()
    cache.set("timed", {"z": 4}, ttl_seconds=1.5)
    _, expires_at = redis._store["tonflow:timed"]
    assert expires_at is not None
    assert expires_at > time()


def test_set_overwrites_existing_key() -> None:
    cache, _ = _make_cache()
    cache.set("k", {"v": 1})
    cache.set("k", {"v": 2})
    assert cache.get("k") == {"v": 2}


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_removes_all_prefixed_keys() -> None:
    cache, redis = _make_cache(prefix="app:")
    cache.set("a", {"x": 1})
    cache.set("b", {"x": 2})
    cache.set("c", {"x": 3})
    cache.clear()
    assert redis._store == {}


def test_clear_does_not_remove_keys_from_other_prefix() -> None:
    cache_a, redis = _make_cache(prefix="a:")
    cache_b = RedisCache(redis, prefix="b:")
    cache_a.set("key", {"x": 1})
    cache_b.set("key", {"y": 2})

    cache_a.clear()

    assert redis._store.get("a:key") is None
    assert redis._store.get("b:key") is not None


def test_clear_on_empty_cache_does_not_raise() -> None:
    cache, _ = _make_cache()
    cache.clear()


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def test_stored_value_is_compact_json() -> None:
    cache, redis = _make_cache()
    cache.set("k", {"b": 2, "a": 1})
    raw = redis._store["tonflow:k"][0].decode()
    assert raw == '{"a":1,"b":2}'


def test_get_raises_on_non_dict_json() -> None:
    cache, redis = _make_cache()
    redis._store["tonflow:bad"] = (json.dumps([1, 2, 3]).encode(), None)
    with pytest.raises(ValueError, match="JSON object"):
        cache.get("bad")
