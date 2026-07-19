"""Tests for SQL export helpers."""

from __future__ import annotations

from decimal import Decimal

from tonflow.export import jetton_transfers_to_sql, transactions_to_sql
from tonflow.models import JettonTransfer, Transaction


def _tx(hash_: str = "abc123", lt: int = 1000) -> Transaction:
    return Transaction.model_validate(
        {"hash": hash_, "lt": lt, "account": "EQowner", "status": "success", "total_fees": 5000}
    )


def _transfer(tx_hash: str = "abc123") -> JettonTransfer:
    return JettonTransfer(
        transaction_hash=tx_hash,
        sender="EQsender",
        recipient="EQrecipient",
        amount=Decimal("1.5"),
        raw_amount=1_500_000_000,
        decimals=9,
        symbol="JETTON",
        jetton_wallet="EQwallet",
        jetton_minter="EQminter",
        comment="hello",
    )


# ---------------------------------------------------------------------------
# transactions_to_sql
# ---------------------------------------------------------------------------


def test_transactions_to_sql_contains_ddl():
    sql = transactions_to_sql([_tx()])
    assert "CREATE TABLE IF NOT EXISTS tonflow_transactions" in sql


def test_transactions_to_sql_no_ddl():
    sql = transactions_to_sql([_tx()], include_ddl=False)
    assert "CREATE TABLE" not in sql
    assert "INSERT INTO" in sql


def test_transactions_to_sql_insert_values():
    sql = transactions_to_sql([_tx(hash_="deadbeef", lt=9999)], include_ddl=False)
    assert "'deadbeef'" in sql
    assert "9999" in sql
    assert "ON CONFLICT (hash) DO NOTHING" in sql


def test_transactions_to_sql_none_timestamp():
    sql = transactions_to_sql([_tx()], include_ddl=False)
    assert "NULL" in sql  # timestamp is None


def test_transactions_to_sql_multiple():
    sql = transactions_to_sql([_tx("h1"), _tx("h2")], include_ddl=False)
    assert sql.count("INSERT INTO") == 2


def test_transactions_to_sql_empty():
    sql = transactions_to_sql([], include_ddl=False)
    assert "INSERT INTO" not in sql


def test_transactions_sql_escapes_single_quotes():
    tx = Transaction.model_validate(
        {"hash": "it's'quoted", "lt": 1, "account": "EQ", "status": "success"}
    )
    sql = transactions_to_sql([tx], include_ddl=False)
    assert "it''s''quoted" in sql


# ---------------------------------------------------------------------------
# jetton_transfers_to_sql
# ---------------------------------------------------------------------------


def test_jetton_transfers_to_sql_contains_ddl():
    sql = jetton_transfers_to_sql([_transfer()])
    assert "CREATE TABLE IF NOT EXISTS tonflow_jetton_transfers" in sql


def test_jetton_transfers_to_sql_insert_values():
    sql = jetton_transfers_to_sql([_transfer()], include_ddl=False)
    assert "'EQsender'" in sql
    assert "'EQrecipient'" in sql
    assert "'1.5'" in sql
    assert "1500000000" in sql
    assert "'JETTON'" in sql


def test_jetton_transfers_to_sql_null_comment():
    t = JettonTransfer(
        transaction_hash="h",
        sender="EQa",
        recipient="EQb",
        amount=Decimal("1"),
        raw_amount=1,
        decimals=9,
        comment=None,
    )
    sql = jetton_transfers_to_sql([t], include_ddl=False)
    assert sql.endswith("NULL);\n")


def test_jetton_transfers_to_sql_multiple():
    sql = jetton_transfers_to_sql([_transfer("h1"), _transfer("h2")], include_ddl=False)
    assert sql.count("INSERT INTO") == 2
