from time import sleep

from tonflow.cache import InMemoryCache, SQLiteCache


def test_in_memory_cache_returns_values() -> None:
    cache = InMemoryCache()
    cache.set("key", {"ok": True})

    assert cache.get("key") == {"ok": True}


def test_in_memory_cache_expires_values() -> None:
    cache = InMemoryCache()
    cache.set("key", "value", ttl_seconds=0.01)

    sleep(0.02)

    assert cache.get("key") is None


def test_sqlite_cache_returns_values(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "tonflow-cache.sqlite3")
    cache.set("key", {"ok": True})

    assert cache.get("key") == {"ok": True}


def test_sqlite_cache_persists_values(tmp_path) -> None:
    path = tmp_path / "tonflow-cache.sqlite3"
    SQLiteCache(path).set("key", {"ok": True})

    assert SQLiteCache(path).get("key") == {"ok": True}


def test_sqlite_cache_expires_values(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "tonflow-cache.sqlite3")
    cache.set("key", {"ok": True}, ttl_seconds=0.01)

    sleep(0.02)

    assert cache.get("key") is None
