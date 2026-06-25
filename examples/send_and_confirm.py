"""Example: broadcast a signed BOC and wait for on-chain confirmation.

TON is fully asynchronous — submitting a message does not guarantee it
was executed. send_and_confirm() solves this by:

  1. Recording the account's latest logical time (baseline LT).
  2. Broadcasting the pre-signed BOC to the network.
  3. Polling every few seconds until a transaction with a higher LT appears.
  4. Raising TonflowExpiredError if valid_until passes before confirmation.
  5. Raising TonflowTimeoutError if the timeout elapses.

This example does not build or sign the BOC — that requires a wallet
library such as pytoniq or tonsdk. Paste a real base64-encoded BOC into
BOC below to try it against a live wallet.

Run:
    python examples/send_and_confirm.py
"""

import asyncio
from time import time

from tonflow import TonClient, TonflowExpiredError, TonflowTimeoutError, send_and_confirm

ENDPOINT = "https://tonapi.io"
API_KEY = ""  # optional — set to avoid rate limits

# The wallet address that signed the message.
WALLET_ADDRESS = "EQ..."

# A pre-built, pre-signed base64 BOC.
# Build this with pytoniq, tonsdk, or any TON wallet SDK.
BOC = ""


async def main() -> None:
    if not BOC:
        print("Set BOC to a real signed base64 message before running this example.")
        return

    async with TonClient(endpoint=ENDPOINT, api_key=API_KEY or None) as client:
        print(f"Broadcasting message from {WALLET_ADDRESS}...")

        try:
            tx = await send_and_confirm(
                client,
                WALLET_ADDRESS,
                BOC,
                timeout=60,
                poll_interval=3,
                valid_until=int(time()) + 60,
            )
        except TonflowExpiredError as e:
            print(f"Message expired before reaching a block: {e}")
            print("Build a new message with an updated seqno and valid_until, then retry.")
            return
        except TonflowTimeoutError as e:
            print(f"Timed out waiting for confirmation: {e}")
            print("The message may still land. Check the address manually.")
            return

        print(f"\nConfirmed on-chain:")
        print(f"  hash           = {tx.hash}")
        print(f"  logical_time   = {tx.logical_time}")
        print(f"  status         = {tx.status}")
        print(f"  fees           = {tx.total_fees}")


if __name__ == "__main__":
    asyncio.run(main())
