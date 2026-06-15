"""Example: use SQLiteCache to avoid hammering public TON nodes.

The first call fetches from the API and stores the result locally.
Subsequent calls within the TTL window are served from the cache.

Run:
    python examples/cache_with_sqlite.py
"""

import asyncio
import time

from tonflow import SQLiteCache, TonClient

ENDPOINT = "https://tonapi.io"
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
CACHE_PATH = ".tonflow/cache.sqlite3"
TTL_SECONDS = 60


async def main() -> None:
    client = TonClient(
        endpoint=ENDPOINT,
        cache=SQLiteCache(CACHE_PATH),
        cache_ttl_seconds=TTL_SECONDS,
    )

    print("First call — fetches from API and writes to cache...")
    t0 = time.monotonic()
    txs = await client.get_transactions(ADDRESS, limit=10)
    print(f"  Got {len(txs)} transactions in {time.monotonic() - t0:.3f}s")

    print("Second call — served from local cache...")
    t1 = time.monotonic()
    txs_cached = await client.get_transactions(ADDRESS, limit=10)
    print(f"  Got {len(txs_cached)} transactions in {time.monotonic() - t1:.3f}s")

    print(f"\nCache stored at: {CACHE_PATH}")
    print(f"TTL: {TTL_SECONDS}s — next call after TTL hits the API again.")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
