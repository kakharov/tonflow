"""Tests for DEX swap event decoding (Ston.fi and DeDust)."""

from __future__ import annotations

from tonflow.dex import (
    OP_DEDUST_SWAP_JETTON,
    OP_DEDUST_SWAP_NATIVE,
    OP_DEDUST_SWAP_POOL,
    OP_STONFI_PAY_TO,
    OP_STONFI_SWAP,
    decode_dedust_swap,
    decode_stonfi_swap,
    extract_dex_swaps,
    is_dedust_swap,
    is_dex_swap,
    is_stonfi_swap,
)
from tonflow.models import (
    DexName,
    DexSwap,
    Message,
    MessageDirection,
    Transaction,
    TransactionStatus,
)


def _tx(hash: str = "abcd1234") -> Transaction:
    return Transaction(
        hash=hash,
        account="0:aaaa",
        lt=1000,
        timestamp=None,
        status=TransactionStatus.SUCCESS,
        in_message=None,
        out_messages=(),
        total_fees=None,
        raw={},
    )


def _msg(op_code: int, raw: dict | None = None, **kwargs: object) -> Message:
    defaults: dict = {
        "source": "0:source",
        "destination": "0:dest",
        "direction": MessageDirection.INBOUND,
        "value": None,
        "body": None,
        "op_code": op_code,
        "raw": raw or {},
    }
    defaults.update(kwargs)
    return Message(**defaults)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def test_is_stonfi_swap_detects_both_ops() -> None:
    assert is_stonfi_swap(_msg(OP_STONFI_SWAP))
    assert is_stonfi_swap(_msg(OP_STONFI_PAY_TO))
    assert not is_stonfi_swap(_msg(0x12345678))


def test_is_dedust_swap_detects_all_ops() -> None:
    assert is_dedust_swap(_msg(OP_DEDUST_SWAP_NATIVE))
    assert is_dedust_swap(_msg(OP_DEDUST_SWAP_JETTON))
    assert is_dedust_swap(_msg(OP_DEDUST_SWAP_POOL))
    assert not is_dedust_swap(_msg(0x12345678))


def test_is_dex_swap_covers_both_dexes() -> None:
    assert is_dex_swap(_msg(OP_STONFI_SWAP))
    assert is_dex_swap(_msg(OP_DEDUST_SWAP_POOL))
    assert not is_dex_swap(_msg(0x00000001))


# ---------------------------------------------------------------------------
# Ston.fi decoding
# ---------------------------------------------------------------------------


def test_decode_stonfi_swap_request() -> None:
    msg = _msg(
        OP_STONFI_SWAP,
        raw={
            "amount": 1_000_000_000,
            "min_out": 500_000_000,
            "sender": "0:user",
            "to_address": "0:receiver",
        },
        source="0:router",
        destination="0:router",
    )
    swap = decode_stonfi_swap(_tx(), msg)
    assert isinstance(swap, DexSwap)
    assert swap.dex == DexName.STONFI
    assert swap.amount_in == 1_000_000_000
    assert swap.amount_out == 500_000_000
    assert swap.sender == "0:user"
    assert swap.receiver == "0:receiver"


def test_decode_stonfi_pay_to() -> None:
    msg = _msg(
        OP_STONFI_PAY_TO,
        raw={
            "amount0_out": 800_000_000,
            "amount1_out": 200_000_000,
            "owner": "0:receiver",
        },
        source="0:pool",
        destination="0:router",
    )
    swap = decode_stonfi_swap(_tx(), msg)
    assert swap is not None
    assert swap.dex == DexName.STONFI
    assert swap.amount_out == 1_000_000_000
    assert swap.receiver == "0:receiver"
    assert swap.router == "0:pool"


def test_decode_stonfi_returns_none_for_unknown_op() -> None:
    assert decode_stonfi_swap(_tx(), _msg(0x99999999)) is None


def test_decode_stonfi_swap_missing_amounts_defaults_to_zero() -> None:
    swap = decode_stonfi_swap(_tx(), _msg(OP_STONFI_SWAP, raw={}))
    assert swap is not None
    assert swap.amount_in == 0
    assert swap.amount_out == 0


# ---------------------------------------------------------------------------
# DeDust decoding
# ---------------------------------------------------------------------------


def test_decode_dedust_swap_native() -> None:
    msg = _msg(
        OP_DEDUST_SWAP_NATIVE,
        raw={"amount": 2_000_000_000, "sender": "0:user", "recipient": "0:vault"},
        source="0:user",
        destination="0:vault",
    )
    swap = decode_dedust_swap(_tx(), msg)
    assert swap is not None
    assert swap.dex == DexName.DEDUST
    assert swap.amount_in == 2_000_000_000
    assert swap.jetton_master_in is None
    assert swap.router == "0:vault"


def test_decode_dedust_swap_native_falls_back_to_message_value() -> None:
    msg = _msg(
        OP_DEDUST_SWAP_NATIVE,
        raw={},
        source="0:user",
        destination="0:vault",
        value=500_000_000,
    )
    swap = decode_dedust_swap(_tx(), msg)
    assert swap is not None
    assert swap.amount_in == 500_000_000


def test_decode_dedust_swap_jetton() -> None:
    msg = _msg(
        OP_DEDUST_SWAP_JETTON,
        raw={
            "amount": 3_000_000_000,
            "jetton_master": "0:jetton_minter",
            "sender": "0:user",
        },
    )
    swap = decode_dedust_swap(_tx(), msg)
    assert swap is not None
    assert swap.dex == DexName.DEDUST
    assert swap.amount_in == 3_000_000_000
    assert swap.jetton_master_in == "0:jetton_minter"


def test_decode_dedust_swap_pool_result() -> None:
    msg = _msg(
        OP_DEDUST_SWAP_POOL,
        raw={
            "amount0": 1_000_000_000,
            "amount1": 4_500_000_000,
            "sender": "0:user",
            "asset0": "0:jetton_in",
            "asset1": "0:jetton_out",
        },
    )
    swap = decode_dedust_swap(_tx(), msg)
    assert swap is not None
    assert swap.dex == DexName.DEDUST
    assert swap.amount_in == 1_000_000_000
    assert swap.amount_out == 4_500_000_000
    assert swap.jetton_master_in == "0:jetton_in"
    assert swap.jetton_master_out == "0:jetton_out"


def test_decode_dedust_returns_none_for_unknown_op() -> None:
    assert decode_dedust_swap(_tx(), _msg(0x99999999)) is None


# ---------------------------------------------------------------------------
# extract_dex_swaps
# ---------------------------------------------------------------------------


def test_extract_dex_swaps_finds_all_messages() -> None:
    stonfi_msg = _msg(
        OP_STONFI_PAY_TO,
        raw={"amount0_out": 1_000_000_000, "amount1_out": 0, "owner": "0:recv"},
        direction=MessageDirection.INBOUND,
    )
    dedust_msg = _msg(
        OP_DEDUST_SWAP_NATIVE,
        raw={"amount": 500_000_000},
        direction=MessageDirection.OUTBOUND,
    )
    tx = Transaction(
        hash="cafebabe",
        account="0:aaaa",
        lt=1001,
        timestamp=None,
        status=TransactionStatus.SUCCESS,
        in_message=stonfi_msg,
        out_messages=(dedust_msg,),
        total_fees=None,
        raw={},
    )
    swaps = extract_dex_swaps(tx)
    assert len(swaps) == 2
    assert swaps[0].dex == DexName.STONFI
    assert swaps[1].dex == DexName.DEDUST


def test_extract_dex_swaps_empty_for_non_dex_tx() -> None:
    msg = _msg(0x00000001)
    tx = Transaction(
        hash="deadbeef",
        account="0:aaaa",
        lt=1002,
        timestamp=None,
        status=TransactionStatus.SUCCESS,
        in_message=msg,
        out_messages=(),
        total_fees=None,
        raw={},
    )
    assert extract_dex_swaps(tx) == []
