from time import sleep

from tonflow.cache import InMemoryCache


def test_in_memory_cache_returns_values() -> None:
    cache = InMemoryCache()
    cache.set("key", {"ok": True})

    assert cache.get("key") == {"ok": True}


def test_in_memory_cache_expires_values() -> None:
    cache = InMemoryCache()
    cache.set("key", "value", ttl_seconds=0.01)

    sleep(0.02)

    assert cache.get("key") is None
