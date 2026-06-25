"""Example: switch to TonCenter as the API provider.

The pluggable provider system lets you swap the underlying API without
changing any application code. TonCenter is free; TonAPI requires a
paid plan for higher rate limits.

Run:
    python examples/toncenter_provider.py
"""

import asyncio

from tonflow import TonClient, TonCenterProvider

# TonCenter public endpoint — api_key is optional but avoids rate limiting.
# Get a free key at https://toncenter.com
TONCENTER_API_KEY = ""

ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


async def main() -> None:
    provider = TonCenterProvider(api_key=TONCENTER_API_KEY or None)

    async with TonClient(provider=provider) as client:
        transactions = await client.get_transactions(ADDRESS, limit=5)

    print(f"Fetched {len(transactions)} transactions via TonCenter\n")
    for tx in transactions:
        print(
            f"  hash={tx.hash[:16]}..."
            f"  lt={tx.logical_time}"
            f"  status={tx.status}"
        )


if __name__ == "__main__":
    asyncio.run(main())
