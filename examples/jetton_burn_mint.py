"""Example: decode Jetton burn and mint events from transactions (TEP-74).

Burn events are emitted when a holder destroys tokens.
Mint events are emitted when the minter contract creates new tokens.

Both are decoded from transaction messages using the TEP-74 op codes:
  - Burn notification: 0x7BDD97DE
  - Internal transfer (mint): 0x178D4519

Run:
    python examples/jetton_burn_mint.py
"""

import asyncio

from tonflow import TonClient, extract_jetton_burns, extract_jetton_mints

ENDPOINT = "https://tonapi.io"

# Address of the Jetton minter contract (the token issuer).
JETTON_MINTER = "EQ..."

# Address to scan for burn/mint transactions.
ADDRESS = "EQ..."

DECIMALS = 9
SYMBOL = "JETTON"


async def main() -> None:
    async with TonClient(endpoint=ENDPOINT) as client:
        transactions = await client.get_transactions(ADDRESS, limit=20)

    burns = []
    mints = []

    for tx in transactions:
        burns.extend(
            extract_jetton_burns(
                tx,
                decimals=DECIMALS,
                jetton_minter=JETTON_MINTER,
                symbol=SYMBOL,
            )
        )
        mints.extend(
            extract_jetton_mints(
                tx,
                decimals=DECIMALS,
                jetton_minter=JETTON_MINTER,
                symbol=SYMBOL,
            )
        )

    print(f"Found {len(burns)} burn(s) and {len(mints)} mint(s) in last {len(transactions)} txs\n")

    for b in burns:
        print(f"  BURN  sender={b.sender}  amount={b.amount} {b.symbol}")

    for m in mints:
        print(f"  MINT  recipient={m.recipient}  amount={m.amount} {m.symbol}")


if __name__ == "__main__":
    asyncio.run(main())
