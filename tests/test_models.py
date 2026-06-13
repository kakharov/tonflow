from decimal import Decimal

import pytest
from pydantic import ValidationError

from tonflow import (
    JettonTransfer,
    Message,
    MessageDirection,
    Transaction,
    TransactionStatus,
)


def test_transaction_accepts_lt_alias() -> None:
    transaction = Transaction(
        hash="abc",
        account="EQ" + "A" * 46,
        lt=123,
        status=TransactionStatus.SUCCESS,
        in_message=Message(
            source=None,
            destination="EQ" + "B" * 46,
            direction=MessageDirection.INBOUND,
            value=1,
        ),
    )

    assert transaction.logical_time == 123
    assert transaction.model_dump(mode="json", by_alias=True)["lt"] == 123


def test_transaction_rejects_negative_logical_time() -> None:
    with pytest.raises(ValidationError):
        Transaction(hash="abc", account="EQ" + "A" * 46, lt=-1)


def test_jetton_transfer_normalizes_blank_symbol() -> None:
    transfer = JettonTransfer(
        transaction_hash="abc",
        sender="EQ" + "A" * 46,
        recipient="EQ" + "B" * 46,
        amount=Decimal("1.25"),
        raw_amount=125,
        decimals=2,
        symbol="   ",
    )

    assert transfer.symbol is None
