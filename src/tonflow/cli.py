"""Command-line interface for tonflow."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tonflow.client import TonClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tonflow",
        description="TON blockchain toolkit — inspect addresses from the command line.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ------------------------------------------------------------------ scan
    scan = sub.add_parser("scan", help="Fetch and display recent transactions for an address.")
    scan.add_argument("address", help="TON account address (user-friendly or raw format).")
    scan.add_argument(
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="Number of transactions to fetch (default: 10).",
    )
    scan.add_argument(
        "--endpoint",
        default="https://tonapi.io",
        metavar="URL",
        help="API endpoint URL (default: https://tonapi.io).",
    )
    scan.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help="API key for the endpoint.",
    )
    scan.add_argument(
        "--provider",
        choices=["tonapi", "toncenter"],
        default="tonapi",
        help="API provider to use (default: tonapi).",
    )

    # ----------------------------------------------------------------- balance
    balance = sub.add_parser("balance", help="Show the TON balance of an address.")
    balance.add_argument("address", help="TON account address.")
    balance.add_argument(
        "--endpoint",
        default="https://tonapi.io",
        metavar="URL",
        help="API endpoint URL (default: https://tonapi.io).",
    )
    balance.add_argument("--api-key", default=None, metavar="KEY", help="API key.")
    balance.add_argument(
        "--provider",
        choices=["tonapi", "toncenter"],
        default="tonapi",
        help="API provider to use (default: tonapi).",
    )

    return parser


def _make_client(args: argparse.Namespace) -> TonClient:
    from tonflow.client import TonClient
    from tonflow.providers import TonCenterProvider

    api_key: str | None = args.api_key
    endpoint: str = args.endpoint

    if args.provider == "toncenter":
        tc_endpoint = endpoint if "toncenter" in endpoint else "https://toncenter.com/api/v2"
        provider = TonCenterProvider(endpoint=tc_endpoint, api_key=api_key)
        return TonClient(provider=provider)

    return TonClient(endpoint=endpoint, api_key=api_key)


async def _cmd_scan(args: argparse.Namespace) -> None:
    client = _make_client(args)
    async with client:
        txs = await client.get_transactions(args.address, limit=args.limit)

    if not txs:
        print("No transactions found.")
        return

    print(f"{'HASH':18}  {'LT':>18}  {'STATUS':8}  {'FEES (nano)':>14}  TIMESTAMP")
    print("-" * 80)
    for tx in txs:
        print(
            f"{tx.hash[:16]}...  "
            f"{tx.logical_time:>18}  "
            f"{tx.status:<8}  "
            f"{(tx.total_fees or 0):>14}  "
            f"{tx.timestamp or '-'}"
        )


async def _cmd_balance(args: argparse.Namespace) -> None:
    client = _make_client(args)
    async with client:
        nanotons = await client.get_balance(args.address)

    ton = nanotons / 1_000_000_000
    print(f"Balance: {ton:.9f} TON  ({nanotons} nanotons)")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "scan":
        asyncio.run(_cmd_scan(args))
    elif args.command == "balance":
        asyncio.run(_cmd_balance(args))


if __name__ == "__main__":
    main()
