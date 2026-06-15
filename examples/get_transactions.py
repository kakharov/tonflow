"""Example: fetch and print recent transactions for a TON address.

Run:
    python examples/get_transactions.py
"""

import asyncio

from tonflow import TonClient

# Public TonAPI endpoint — no API key needed for low-volume usage.
ENDPOINT = "https://tonapi.io"

# Replace with any mainnet address you want to inspect.
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


async def main() -> None:
    async with TonClient(endpoint=ENDPOINT) as client:
        transactions = await client.get_transactions(ADDRESS, limit=10)

    print(f"Fetched {len(transactions)} transactions for {ADDRESS}\n")
    for tx in transactions:
        print(
            f"  hash={tx.hash[:16]}..."
            f"  lt={tx.logical_time}"
            f"  status={tx.status}"
            f"  fees={tx.total_fees}"
        )


if __name__ == "__main__":
    asyncio.run(main())
