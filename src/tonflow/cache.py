"""Small cache primitives used by clients and streams."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry[T]:
    value: T
    expires_at: float | None


class InMemoryCache:
    """Simple TTL cache for tests, examples, and short-lived scripts."""

    def __init__(self) -> None:
        self._items: dict[str, _CacheEntry[object]] = {}

    def get[T](self, key: str) -> T | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and entry.expires_at <= monotonic():
            self._items.pop(key, None)
            return None
        return entry.value  # type: ignore[return-value]

    def set(self, key: str, value: object, ttl_seconds: float | None = None) -> None:
        expires_at = None if ttl_seconds is None else monotonic() + ttl_seconds
        self._items[key] = _CacheEntry(value=value, expires_at=expires_at)

    def clear(self) -> None:
        self._items.clear()
