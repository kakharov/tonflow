"""Example: fetch Jetton transfers and save them to a CSV file.

Run:
    python examples/export_to_csv.py
"""

import asyncio
from pathlib import Path

from tonflow import TonClient, jetton_transfers_to_csv, transactions_to_csv

ENDPOINT = "https://tonapi.io"
ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
OUTPUT_DIR = Path("output")


async def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with TonClient(endpoint=ENDPOINT) as client:
        transactions = await client.get_transactions(ADDRESS, limit=50)
        transfers = await client.get_jetton_transfers(ADDRESS, limit=50, decimals=9)

    tx_path = OUTPUT_DIR / "transactions.csv"
    tx_path.write_text(transactions_to_csv(transactions), encoding="utf-8")
    print(f"Saved {len(transactions)} transactions → {tx_path}")

    transfers_path = OUTPUT_DIR / "jetton_transfers.csv"
    transfers_path.write_text(jetton_transfers_to_csv(transfers), encoding="utf-8")
    print(f"Saved {len(transfers)} Jetton transfers → {transfers_path}")


if __name__ == "__main__":
    asyncio.run(main())
