"""Example: stream new transactions in real time via WebSocket (TonAPI).

Unlike watch_address() which polls on a fixed interval, WebSocket streaming
receives push notifications the moment a transaction lands on-chain.

Requires the ws extra:
    pip install tonflow[ws]

Run:
    python examples/stream_websocket.py
"""

import asyncio

from tonflow import TonClient
from tonflow.websocket import stream_transactions_ws

ENDPOINT = "https://tonapi.io"
API_KEY = ""  # recommended — unauthenticated connections have stricter rate limits

ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

# Stop after this many transactions (set to None to run indefinitely).
MAX_TXS = 5


async def main() -> None:
    async with TonClient(endpoint=ENDPOINT, api_key=API_KEY or None) as client:
        print(f"Listening for transactions on {ADDRESS} via WebSocket...")
        print("Press Ctrl+C to stop.\n")

        count = 0
        async for tx in stream_transactions_ws(client, ADDRESS, api_key=API_KEY or None):
            print(f"  [{count + 1}] hash={tx.hash[:16]}...  lt={tx.logical_time}  status={tx.status}")
            count += 1
            if MAX_TXS is not None and count >= MAX_TXS:
                print(f"\nReached {MAX_TXS} transactions. Stopping.")
                break


if __name__ == "__main__":
    asyncio.run(main())
