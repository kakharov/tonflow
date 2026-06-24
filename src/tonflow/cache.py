"""Small cache primitives used by clients and streams."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, time
from typing import Any, Protocol, TypeVar

from tonflow.models import RawPayload

T = TypeVar("T")


class JSONCache(Protocol):
    """Cache backend interface for JSON-compatible API responses."""

    def get(self, key: str) -> RawPayload | None:
        """Return a cached JSON payload or None when it is missing/expired."""

    def set(self, key: str, value: RawPayload, ttl_seconds: float | None = None) -> None:
        """Store a JSON payload with an optional TTL."""

    def clear(self) -> None:
        """Remove all cached values."""


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


class SQLiteCache:
    """SQLite-backed TTL cache for local scripts and small services."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get(self, key: str) -> RawPayload | None:
        now = time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None

            value, expires_at = row
            if expires_at is not None and expires_at <= now:
                connection.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                return None

        data = json.loads(value)
        if not isinstance(data, dict):
            msg = "Cached payload must be a JSON object."
            raise ValueError(msg)
        return data

    def set(self, key: str, value: RawPayload, ttl_seconds: float | None = None) -> None:
        expires_at = None if ttl_seconds is None else time() + ttl_seconds
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries (key, value, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at
                """,
                (key, encoded, expires_at),
            )

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


class RedisCache:
    """Redis-backed TTL cache for production services.

    Requires the ``redis`` extra::

        pip install tonflow[redis]

    Pass any ``redis.Redis`` (or compatible) client — sync or async wrappers
    are not supported; use the standard synchronous client::

        import redis
        client = redis.Redis(host="localhost", port=6379, db=0)
        cache = RedisCache(client, prefix="myapp:")

    The ``prefix`` isolates keys so multiple apps can share one Redis instance
    without collisions.
    """

    def __init__(self, client: Any, *, prefix: str = "tonflow:") -> None:
        self._client = client
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> RawPayload | None:
        raw = self._client.get(self._key(key))
        if raw is None:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            msg = "Cached payload must be a JSON object."
            raise ValueError(msg)
        return data

    def set(self, key: str, value: RawPayload, ttl_seconds: float | None = None) -> None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if ttl_seconds is not None:
            self._client.set(self._key(key), encoded, px=int(ttl_seconds * 1000))
        else:
            self._client.set(self._key(key), encoded)

    def clear(self) -> None:
        """Delete all keys matching this cache's prefix.

        Uses Redis SCAN to avoid blocking the server on large keyspaces.
        """
        pattern = f"{self._prefix}*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break
