"""Helpers for exporting tonflow models to JSON and CSV."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any

from tonflow.models import JettonTransfer, Transaction


def _default(obj: object) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def transactions_to_json(transactions: list[Transaction], *, indent: int | None = None) -> str:
    """Serialize a list of transactions to a JSON string.

    Decimal values are serialized as strings to preserve precision.
    """
    data = [tx.model_dump(mode="json") for tx in transactions]
    return json.dumps(data, default=_default, indent=indent, ensure_ascii=False)


def jetton_transfers_to_json(transfers: list[JettonTransfer], *, indent: int | None = None) -> str:
    """Serialize a list of Jetton transfers to a JSON string."""
    data = [t.model_dump(mode="json") for t in transfers]
    return json.dumps(data, default=_default, indent=indent, ensure_ascii=False)


# CSV column ordering for each model type
_TRANSACTION_FIELDS = [
    "hash",
    "account",
    "logical_time",
    "timestamp",
    "status",
    "total_fees",
]

_JETTON_TRANSFER_FIELDS = [
    "transaction_hash",
    "sender",
    "recipient",
    "amount",
    "raw_amount",
    "decimals",
    "symbol",
    "jetton_wallet",
    "jetton_minter",
    "comment",
]


def transactions_to_csv(transactions: list[Transaction]) -> str:
    """Serialize a list of transactions to a CSV string.

    Includes the core scalar fields; nested messages and raw payload are omitted.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_TRANSACTION_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for tx in transactions:
        writer.writerow(
            {
                "hash": tx.hash,
                "account": tx.account,
                "logical_time": tx.logical_time,
                "timestamp": tx.timestamp,
                "status": tx.status,
                "total_fees": tx.total_fees,
            }
        )
    return output.getvalue()


def jetton_transfers_to_csv(transfers: list[JettonTransfer]) -> str:
    """Serialize a list of Jetton transfers to a CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_JETTON_TRANSFER_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for t in transfers:
        writer.writerow(
            {
                "transaction_hash": t.transaction_hash,
                "sender": t.sender,
                "recipient": t.recipient,
                "amount": str(t.amount),
                "raw_amount": t.raw_amount,
                "decimals": t.decimals,
                "symbol": t.symbol,
                "jetton_wallet": t.jetton_wallet,
                "jetton_minter": t.jetton_minter,
                "comment": t.comment,
            }
        )
    return output.getvalue()
