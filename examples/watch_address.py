"""Example: stream new transactions for a TON address in real time.

Polls the address every 5 seconds and prints each new transaction as it arrives.
Press Ctrl+C to stop.

Run:
    python examples/watch_address.py
"""

import asyncio

from tonflow import TonClient, watch_address

ENDPOINT = "https://tonapi.io"
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


async def main() -> None:
    print(f"Watching {ADDRESS} for new transactions (Ctrl+C to stop)...\n")

    async with TonClient(endpoint=ENDPOINT) as client:
        async for tx in watch_address(client, ADDRESS, interval_seconds=5):
            print(f"  New tx: hash={tx.hash[:16]}...  lt={tx.logical_time}  status={tx.status}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
