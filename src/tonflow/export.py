"""Helpers for exporting tonflow models to JSON, CSV, and SQL."""

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


_TRANSACTIONS_DDL = """\
CREATE TABLE IF NOT EXISTS tonflow_transactions (
    hash TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    logical_time BIGINT NOT NULL,
    timestamp BIGINT,
    status TEXT,
    total_fees BIGINT
);
"""

_JETTON_TRANSFERS_DDL = """\
CREATE TABLE IF NOT EXISTS tonflow_jetton_transfers (
    transaction_hash TEXT NOT NULL,
    sender TEXT,
    recipient TEXT,
    amount TEXT NOT NULL,
    raw_amount BIGINT NOT NULL,
    decimals INTEGER NOT NULL,
    symbol TEXT,
    jetton_wallet TEXT,
    jetton_minter TEXT,
    comment TEXT
);
"""


def _escape(value: object) -> str:
    """Render a Python value as a SQL literal (strings single-quoted, NULL for None)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def transactions_to_sql(transactions: list[Transaction], *, include_ddl: bool = True) -> str:
    """Generate Postgres-compatible SQL for a list of transactions.

    Produces ``CREATE TABLE IF NOT EXISTS`` (when *include_ddl* is True) and
    ``INSERT … ON CONFLICT (hash) DO NOTHING`` statements. Execute the result
    with psycopg2, asyncpg, or any Postgres client.

    Args:
        transactions: Transactions to export.
        include_ddl: Prepend the ``CREATE TABLE`` statement.

    Returns:
        A SQL string ready to execute.
    """
    lines: list[str] = []
    if include_ddl:
        lines.append(_TRANSACTIONS_DDL)
    for tx in transactions:
        vals = ", ".join(
            [
                _escape(tx.hash),
                _escape(tx.account),
                _escape(tx.logical_time),
                _escape(tx.timestamp),
                _escape(tx.status),
                _escape(tx.total_fees),
            ]
        )
        lines.append(
            f"INSERT INTO tonflow_transactions "
            f"(hash, account, logical_time, timestamp, status, total_fees) "
            f"VALUES ({vals}) ON CONFLICT (hash) DO NOTHING;"
        )
    return "\n".join(lines) + "\n"


def jetton_transfers_to_sql(transfers: list[JettonTransfer], *, include_ddl: bool = True) -> str:
    """Generate Postgres-compatible SQL for a list of Jetton transfers.

    Args:
        transfers: Transfers to export.
        include_ddl: Prepend the ``CREATE TABLE`` statement.

    Returns:
        A SQL string ready to execute.
    """
    lines: list[str] = []
    if include_ddl:
        lines.append(_JETTON_TRANSFERS_DDL)
    for t in transfers:
        vals = ", ".join(
            [
                _escape(t.transaction_hash),
                _escape(t.sender),
                _escape(t.recipient),
                _escape(str(t.amount)),
                _escape(t.raw_amount),
                _escape(t.decimals),
                _escape(t.symbol),
                _escape(t.jetton_wallet),
                _escape(t.jetton_minter),
                _escape(t.comment),
            ]
        )
        lines.append(
            f"INSERT INTO tonflow_jetton_transfers "
            f"(transaction_hash, sender, recipient, amount, raw_amount, "
            f"decimals, symbol, jetton_wallet, jetton_minter, comment) "
            f"VALUES ({vals});"
        )
    return "\n".join(lines) + "\n"


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
