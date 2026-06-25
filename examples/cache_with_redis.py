"""Example: use Redis as the cache backend (production services).

RedisCache stores API responses in Redis with a TTL so that repeated
calls for the same address and parameters are served from cache.

Requires the redis extra:
    pip install tonflow[redis]

Run (requires a local Redis instance):
    redis-server &
    python examples/cache_with_redis.py
"""

import asyncio
import time

import redis

from tonflow import RedisCache, TonClient

ENDPOINT = "https://tonapi.io"
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

REDIS_HOST = "localhost"
REDIS_PORT = 6379


async def main() -> None:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=False)
    cache = RedisCache(redis_client, prefix="tonflow:example:")

    client = TonClient(
        endpoint=ENDPOINT,
        cache=cache,
        cache_ttl_seconds=30,
    )

    async with client:
        print("First fetch — hits the network...")
        t0 = time.perf_counter()
        txs = await client.get_transactions(ADDRESS, limit=10)
        elapsed = time.perf_counter() - t0
        print(f"  {len(txs)} transactions in {elapsed:.2f}s")

        print("\nSecond fetch — served from Redis cache...")
        t0 = time.perf_counter()
        txs_cached = await client.get_transactions(ADDRESS, limit=10)
        elapsed = time.perf_counter() - t0
        print(f"  {len(txs_cached)} transactions in {elapsed:.4f}s")

    print("\nCache entries can be cleared with cache.clear()")
    cache.clear()
    print("Cache cleared.")


if __name__ == "__main__":
    asyncio.run(main())
