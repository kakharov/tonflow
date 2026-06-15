"""Tests for JSON and CSV export helpers."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal

from tonflow.export import (
    jetton_transfers_to_csv,
    jetton_transfers_to_json,
    transactions_to_csv,
    transactions_to_json,
)
from tonflow.models import JettonTransfer, Transaction, TransactionStatus

TX_HASH = "abc123"
ACCOUNT = "EQ" + "A" * 46


def _tx(**kwargs) -> Transaction:  # type: ignore[no-untyped-def]
    defaults = dict(hash=TX_HASH, account=ACCOUNT, lt=1000, status=TransactionStatus.SUCCESS)
    return Transaction(**{**defaults, **kwargs})


def _transfer(**kwargs) -> JettonTransfer:  # type: ignore[no-untyped-def]
    defaults = dict(
        transaction_hash=TX_HASH,
        sender="EQ" + "S" * 46,
        recipient="EQ" + "R" * 46,
        amount=Decimal("1.5"),
        raw_amount=1_500_000_000,
        decimals=9,
        symbol="USDT",
    )
    return JettonTransfer(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# transactions_to_json
# ---------------------------------------------------------------------------


def test_transactions_to_json_returns_list() -> None:
    result = json.loads(transactions_to_json([_tx()]))
    assert isinstance(result, list)
    assert len(result) == 1


def test_transactions_to_json_contains_core_fields() -> None:
    result = json.loads(transactions_to_json([_tx()]))[0]
    assert result["hash"] == TX_HASH
    assert result["account"] == ACCOUNT
    assert result["status"] == "success"


def test_transactions_to_json_empty_list() -> None:
    assert json.loads(transactions_to_json([])) == []


def test_transactions_to_json_multiple() -> None:
    txs = [_tx(hash="tx1", lt=1), _tx(hash="tx2", lt=2)]
    result = json.loads(transactions_to_json(txs))
    assert len(result) == 2
    assert result[0]["hash"] == "tx1"
    assert result[1]["hash"] == "tx2"


def test_transactions_to_json_indent() -> None:
    result = transactions_to_json([_tx()], indent=2)
    assert "\n" in result


# ---------------------------------------------------------------------------
# jetton_transfers_to_json
# ---------------------------------------------------------------------------


def test_jetton_transfers_to_json_serializes_decimal_as_string() -> None:
    result = json.loads(jetton_transfers_to_json([_transfer()]))
    assert result[0]["amount"] == "1.5"


def test_jetton_transfers_to_json_contains_core_fields() -> None:
    result = json.loads(jetton_transfers_to_json([_transfer()]))[0]
    assert result["transaction_hash"] == TX_HASH
    assert result["raw_amount"] == 1_500_000_000
    assert result["symbol"] == "USDT"


def test_jetton_transfers_to_json_empty_list() -> None:
    assert json.loads(jetton_transfers_to_json([])) == []


def test_jetton_transfers_to_json_none_fields() -> None:
    result = json.loads(jetton_transfers_to_json([_transfer(symbol=None, comment=None)]))[0]
    assert result["symbol"] is None
    assert result["comment"] is None


# ---------------------------------------------------------------------------
# transactions_to_csv
# ---------------------------------------------------------------------------


def test_transactions_to_csv_has_header() -> None:
    csv_str = transactions_to_csv([_tx()])
    reader = csv.DictReader(io.StringIO(csv_str))
    assert reader.fieldnames is not None
    assert "hash" in reader.fieldnames
    assert "status" in reader.fieldnames


def test_transactions_to_csv_has_correct_values() -> None:
    csv_str = transactions_to_csv([_tx(lt=9999, timestamp=1700000000)])
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["hash"] == TX_HASH
    assert rows[0]["logical_time"] == "9999"
    assert rows[0]["timestamp"] == "1700000000"
    assert rows[0]["status"] == "success"


def test_transactions_to_csv_empty_list() -> None:
    csv_str = transactions_to_csv([])
    reader = csv.DictReader(io.StringIO(csv_str))
    assert list(reader) == []


def test_transactions_to_csv_multiple_rows() -> None:
    txs = [_tx(hash="tx1", lt=1), _tx(hash="tx2", lt=2)]
    rows = list(csv.DictReader(io.StringIO(transactions_to_csv(txs))))
    assert len(rows) == 2
    assert rows[0]["hash"] == "tx1"
    assert rows[1]["hash"] == "tx2"


# ---------------------------------------------------------------------------
# jetton_transfers_to_csv
# ---------------------------------------------------------------------------


def test_jetton_transfers_to_csv_has_header() -> None:
    csv_str = jetton_transfers_to_csv([_transfer()])
    reader = csv.DictReader(io.StringIO(csv_str))
    assert reader.fieldnames is not None
    assert "amount" in reader.fieldnames
    assert "symbol" in reader.fieldnames


def test_jetton_transfers_to_csv_amount_as_string() -> None:
    rows = list(csv.DictReader(io.StringIO(jetton_transfers_to_csv([_transfer()]))))
    assert rows[0]["amount"] == "1.5"
    assert rows[0]["raw_amount"] == "1500000000"


def test_jetton_transfers_to_csv_empty_list() -> None:
    csv_str = jetton_transfers_to_csv([])
    reader = csv.DictReader(io.StringIO(csv_str))
    assert list(reader) == []


def test_jetton_transfers_to_csv_none_fields_as_empty() -> None:
    rows = list(
        csv.DictReader(io.StringIO(jetton_transfers_to_csv([_transfer(symbol=None, comment=None)])))
    )
    assert rows[0]["symbol"] == ""
    assert rows[0]["comment"] == ""
