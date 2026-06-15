"""Example: fetch Jetton transfers for a TON address.

Scans the last N transactions and prints every Jetton transfer found,
including sender, recipient, human-readable amount, and symbol.

Run:
    python examples/get_jetton_transfers.py
"""

import asyncio

from tonflow import TonClient

ENDPOINT = "https://tonapi.io"

# Replace with a Jetton wallet address or any address that receives token transfers.
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

# Adjust decimals and symbol to match the Jetton you're inspecting.
# USDT on TON uses 6 decimals; native Jettons typically use 9.
DECIMALS = 9
SYMBOL = "TOKEN"


async def main() -> None:
    async with TonClient(endpoint=ENDPOINT) as client:
        transfers = await client.get_jetton_transfers(
            ADDRESS,
            limit=20,
            decimals=DECIMALS,
            symbol=SYMBOL,
        )

    if not transfers:
        print("No Jetton transfers found in the last 20 transactions.")
        return

    print(f"Found {len(transfers)} Jetton transfer(s) for {ADDRESS}\n")
    for t in transfers:
        print(
            f"  tx={t.transaction_hash[:16]}..."
            f"  {t.sender[:12]}... → {t.recipient[:12] if t.recipient else 'unknown'}..."
            f"  amount={t.amount} {t.symbol or ''}"
        )


if __name__ == "__main__":
    asyncio.run(main())
