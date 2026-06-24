"""Tests for Jetton transfer normalization."""

from decimal import Decimal

import pytest

from tonflow.jettons import (
    OP_JETTON_BURN,
    OP_JETTON_INTERNAL_TRANSFER,
    OP_JETTON_TRANSFER,
    OP_JETTON_TRANSFER_NOTIFICATION,
    decode_jetton_burn,
    decode_jetton_mint,
    decode_jetton_transfer,
    extract_jetton_burns,
    extract_jetton_mints,
    extract_jetton_transfers,
    is_jetton_burn,
    is_jetton_mint,
    is_jetton_transfer,
    is_jetton_transfer_notification,
    normalize_amount,
)
from tonflow.models import Message, MessageDirection, Transaction, TransactionStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SENDER = "EQSender1111111111111111111111111111111111111111"
RECIPIENT = "EQRecipient222222222222222222222222222222222222"
WALLET = "EQWallet3333333333333333333333333333333333333333"
MINTER = "EQMinter4444444444444444444444444444444444444444"
TX_HASH = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab"


def _make_transaction(
    in_message: Message | None = None,
    out_messages: tuple[Message, ...] = (),
) -> Transaction:
    return Transaction(
        hash=TX_HASH,
        account=SENDER,
        lt=12345678,
        timestamp=1700000000,
        status=TransactionStatus.SUCCESS,
        in_message=in_message,
        out_messages=out_messages,
    )


def _make_transfer_message(
    op_code: int = OP_JETTON_TRANSFER,
    amount: int = 1_000_000_000,
    source: str = SENDER,
    destination: str = WALLET,
    comment: str | None = None,
) -> Message:
    raw: dict = {"amount": str(amount)}
    if comment:
        raw["forward_payload"] = comment
    return Message(
        source=source,
        destination=destination,
        direction=MessageDirection.INBOUND,
        value=amount,
        op_code=op_code,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# normalize_amount
# ---------------------------------------------------------------------------


def test_normalize_amount_9_decimals() -> None:
    assert normalize_amount(1_000_000_000, 9) == Decimal("1")


def test_normalize_amount_6_decimals() -> None:
    assert normalize_amount(123456789, 6) == Decimal("123.456789")


def test_normalize_amount_zero() -> None:
    assert normalize_amount(0, 9) == Decimal("0")


def test_normalize_amount_string_input() -> None:
    assert normalize_amount("500000000", 9) == Decimal("0.5")


# ---------------------------------------------------------------------------
# op_code predicates
# ---------------------------------------------------------------------------


def test_is_jetton_transfer_true() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER)
    assert is_jetton_transfer(msg) is True


def test_is_jetton_transfer_false() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER_NOTIFICATION)
    assert is_jetton_transfer(msg) is False


def test_is_jetton_transfer_notification() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER_NOTIFICATION)
    assert is_jetton_transfer_notification(msg) is True


def test_is_jetton_burn() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_BURN)
    assert is_jetton_burn(msg) is True


# ---------------------------------------------------------------------------
# decode_jetton_transfer
# ---------------------------------------------------------------------------


def test_decode_transfer_basic() -> None:
    msg = _make_transfer_message(amount=2_000_000_000)
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_transfer(tx, msg, decimals=9, symbol="TON")

    assert result is not None
    assert result.transaction_hash == TX_HASH
    assert result.raw_amount == 2_000_000_000
    assert result.amount == Decimal("2")
    assert result.decimals == 9
    assert result.symbol == "TON"
    assert result.sender == SENDER
    assert result.jetton_wallet == WALLET


def test_decode_transfer_with_comment() -> None:
    msg = _make_transfer_message(amount=500_000_000, comment="hello")
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_transfer(tx, msg, decimals=9)

    assert result is not None
    assert result.comment == "hello"


def test_decode_transfer_notification() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER_NOTIFICATION, amount=1_000_000)
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_transfer(tx, msg, decimals=6, jetton_minter=MINTER)

    assert result is not None
    assert result.amount == Decimal("1")
    assert result.jetton_minter == MINTER


def test_decode_transfer_wrong_opcode_returns_none() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_BURN)
    tx = _make_transaction(in_message=msg)
    assert decode_jetton_transfer(tx, msg) is None


def test_decode_transfer_no_amount_falls_back_to_value() -> None:
    msg = Message(
        source=SENDER,
        destination=WALLET,
        op_code=OP_JETTON_TRANSFER,
        value=750_000_000,
        raw={},
    )
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_transfer(tx, msg, decimals=9)

    assert result is not None
    assert result.raw_amount == 750_000_000


# ---------------------------------------------------------------------------
# extract_jetton_transfers
# ---------------------------------------------------------------------------


def test_extract_from_inbound_message() -> None:
    msg = _make_transfer_message(amount=1_000_000_000)
    tx = _make_transaction(in_message=msg)
    transfers = extract_jetton_transfers(tx, decimals=9)

    assert len(transfers) == 1
    assert transfers[0].amount == Decimal("1")


def test_extract_from_out_messages() -> None:
    out1 = _make_transfer_message(amount=1_000_000_000)
    out2 = _make_transfer_message(op_code=OP_JETTON_TRANSFER_NOTIFICATION, amount=2_000_000_000)
    tx = _make_transaction(out_messages=(out1, out2))
    transfers = extract_jetton_transfers(tx, decimals=9)

    assert len(transfers) == 2


def test_extract_skips_non_jetton_messages() -> None:
    regular_msg = Message(source=SENDER, destination=RECIPIENT, op_code=0x0, raw={})
    tx = _make_transaction(in_message=regular_msg)
    transfers = extract_jetton_transfers(tx)

    assert transfers == []


def test_extract_no_messages() -> None:
    tx = _make_transaction()
    assert extract_jetton_transfers(tx) == []


@pytest.mark.parametrize(
    "raw_amount,decimals,expected",
    [
        (1_000_000_000, 9, Decimal("1")),
        (1_000_000, 6, Decimal("1")),
        (100, 2, Decimal("1")),
        (1, 0, Decimal("1")),
    ],
)
def test_normalize_amount_parametrized(raw_amount: int, decimals: int, expected: Decimal) -> None:
    assert normalize_amount(raw_amount, decimals) == expected


# ---------------------------------------------------------------------------
# is_jetton_mint
# ---------------------------------------------------------------------------


def test_is_jetton_mint_true() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_INTERNAL_TRANSFER)
    assert is_jetton_mint(msg) is True


def test_is_jetton_mint_false_for_transfer() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER)
    assert is_jetton_mint(msg) is False


# ---------------------------------------------------------------------------
# decode_jetton_burn
# ---------------------------------------------------------------------------


def _make_burn_message(
    amount: int = 1_000_000_000,
    source: str = WALLET,
    destination: str = MINTER,
) -> Message:
    return Message(
        source=source,
        destination=destination,
        direction=MessageDirection.OUTBOUND,
        value=amount,
        op_code=OP_JETTON_BURN,
        raw={"amount": str(amount)},
    )


def test_decode_burn_basic() -> None:
    msg = _make_burn_message(amount=5_000_000_000)
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_burn(tx, msg, decimals=9, symbol="USDT")

    assert result is not None
    assert result.transaction_hash == TX_HASH
    assert result.raw_amount == 5_000_000_000
    assert result.amount == Decimal("5")
    assert result.decimals == 9
    assert result.symbol == "USDT"
    assert result.sender == WALLET
    assert result.jetton_wallet == WALLET
    assert result.jetton_minter == MINTER


def test_decode_burn_wrong_opcode_returns_none() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER)
    tx = _make_transaction(in_message=msg)
    assert decode_jetton_burn(tx, msg) is None


def test_decode_burn_explicit_minter() -> None:
    msg = _make_burn_message()
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_burn(tx, msg, jetton_minter="EQ" + "X" * 46)

    assert result is not None
    assert result.jetton_minter == "EQ" + "X" * 46


def test_decode_burn_falls_back_minter_to_destination() -> None:
    msg = _make_burn_message(destination=MINTER)
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_burn(tx, msg)

    assert result is not None
    assert result.jetton_minter == MINTER


# ---------------------------------------------------------------------------
# decode_jetton_mint
# ---------------------------------------------------------------------------


def _make_mint_message(
    amount: int = 2_000_000_000,
    source: str = MINTER,
    destination: str = WALLET,
) -> Message:
    return Message(
        source=source,
        destination=destination,
        direction=MessageDirection.INBOUND,
        value=amount,
        op_code=OP_JETTON_INTERNAL_TRANSFER,
        raw={"amount": str(amount)},
    )


def test_decode_mint_basic() -> None:
    msg = _make_mint_message(amount=10_000_000_000)
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_mint(tx, msg, decimals=9, symbol="SCALE")

    assert result is not None
    assert result.transaction_hash == TX_HASH
    assert result.raw_amount == 10_000_000_000
    assert result.amount == Decimal("10")
    assert result.decimals == 9
    assert result.symbol == "SCALE"
    assert result.recipient == WALLET
    assert result.jetton_wallet == WALLET
    assert result.jetton_minter == MINTER


def test_decode_mint_wrong_opcode_returns_none() -> None:
    msg = _make_transfer_message(op_code=OP_JETTON_TRANSFER)
    tx = _make_transaction(in_message=msg)
    assert decode_jetton_mint(tx, msg) is None


def test_decode_mint_explicit_minter() -> None:
    msg = _make_mint_message()
    tx = _make_transaction(in_message=msg)
    result = decode_jetton_mint(tx, msg, jetton_minter="EQ" + "M" * 46)

    assert result is not None
    assert result.jetton_minter == "EQ" + "M" * 46


# ---------------------------------------------------------------------------
# extract_jetton_burns / extract_jetton_mints
# ---------------------------------------------------------------------------


def test_extract_burns_from_out_messages() -> None:
    burn = _make_burn_message(amount=3_000_000_000)
    tx = _make_transaction(out_messages=(burn,))
    burns = extract_jetton_burns(tx, decimals=9)

    assert len(burns) == 1
    assert burns[0].amount == Decimal("3")


def test_extract_burns_skips_non_burn_messages() -> None:
    tx = _make_transaction(in_message=_make_transfer_message())
    assert extract_jetton_burns(tx) == []


def test_extract_mints_from_in_message() -> None:
    mint = _make_mint_message(amount=7_000_000_000)
    tx = _make_transaction(in_message=mint)
    mints = extract_jetton_mints(tx, decimals=9)

    assert len(mints) == 1
    assert mints[0].amount == Decimal("7")


def test_extract_mints_skips_non_mint_messages() -> None:
    tx = _make_transaction(in_message=_make_transfer_message())
    assert extract_jetton_mints(tx) == []
