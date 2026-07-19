"""Tests for NFT transfer event decoding (TEP-62)."""

from __future__ import annotations

from tonflow.models import Message, MessageDirection, NftTransfer, Transaction
from tonflow.nfts import (
    OP_NFT_OWNERSHIP_ASSIGNED,
    OP_NFT_TRANSFER,
    decode_nft_transfer,
    extract_nft_transfers,
    is_nft_ownership_assigned,
    is_nft_transfer,
)


def _tx(hash_: str = "txhash") -> Transaction:
    return Transaction.model_validate(
        {"hash": hash_, "lt": 1, "account": "EQowner", "status": "success"}
    )


def _msg(
    op_code: int | None = None,
    source: str | None = None,
    destination: str | None = None,
    direction: MessageDirection = MessageDirection.INBOUND,
    raw: dict | None = None,
) -> Message:
    return Message(
        source=source,
        destination=destination,
        direction=direction,
        op_code=op_code,
        raw=raw or {},
    )


# ---------------------------------------------------------------------------
# is_nft_transfer / is_nft_ownership_assigned
# ---------------------------------------------------------------------------


def test_is_nft_transfer_true():
    assert is_nft_transfer(_msg(op_code=OP_NFT_TRANSFER)) is True


def test_is_nft_transfer_false():
    assert is_nft_transfer(_msg(op_code=0xDEADBEEF)) is False


def test_is_nft_transfer_none_opcode():
    assert is_nft_transfer(_msg(op_code=None)) is False


def test_is_nft_ownership_assigned_true():
    assert is_nft_ownership_assigned(_msg(op_code=OP_NFT_OWNERSHIP_ASSIGNED)) is True


def test_is_nft_ownership_assigned_false():
    assert is_nft_ownership_assigned(_msg(op_code=OP_NFT_TRANSFER)) is False


# ---------------------------------------------------------------------------
# decode_nft_transfer — transfer op
# ---------------------------------------------------------------------------


def test_decode_transfer_basic():
    msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
        raw={"new_owner": "EQrecipient"},
    )
    result = decode_nft_transfer(_tx(), msg)
    assert isinstance(result, NftTransfer)
    assert result.sender == "EQsender"
    assert result.recipient == "EQrecipient"
    assert result.nft_address == "EQnft_item"
    assert result.transaction_hash == "txhash"


def test_decode_transfer_recipient_fallback_to_destination():
    """When new_owner is absent, destination is used as recipient."""
    msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
    )
    result = decode_nft_transfer(_tx(), msg)
    assert result is not None
    assert result.recipient == "EQnft_item"


def test_decode_transfer_with_comment():
    msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
        raw={"new_owner": "EQrecipient", "forward_payload": "hello nft"},
    )
    result = decode_nft_transfer(_tx(), msg)
    assert result is not None
    assert result.comment == "hello nft"


def test_decode_transfer_with_collection():
    msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
        raw={"new_owner": "EQrecipient"},
    )
    result = decode_nft_transfer(_tx(), msg, nft_collection="EQcollection")
    assert result is not None
    assert result.nft_collection == "EQcollection"


def test_decode_transfer_collection_from_raw():
    msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
        raw={"new_owner": "EQrecipient", "nft_collection": "EQcollection_raw"},
    )
    result = decode_nft_transfer(_tx(), msg)
    assert result is not None
    assert result.nft_collection == "EQcollection_raw"


def test_decode_transfer_returns_none_for_wrong_opcode():
    msg = _msg(op_code=0x12345678, source="EQsender", destination="EQdst")
    assert decode_nft_transfer(_tx(), msg) is None


def test_decode_transfer_returns_none_for_no_opcode():
    msg = _msg(op_code=None, source="EQsender", destination="EQdst")
    assert decode_nft_transfer(_tx(), msg) is None


# ---------------------------------------------------------------------------
# decode_nft_transfer — ownership_assigned op
# ---------------------------------------------------------------------------


def test_decode_ownership_assigned_basic():
    msg = _msg(
        op_code=OP_NFT_OWNERSHIP_ASSIGNED,
        source="EQnft_item",
        destination="EQnew_owner",
        raw={"prev_owner": "EQold_owner"},
    )
    result = decode_nft_transfer(_tx(), msg)
    assert isinstance(result, NftTransfer)
    assert result.sender == "EQold_owner"
    assert result.recipient == "EQnew_owner"
    assert result.nft_address == "EQnft_item"


def test_decode_ownership_assigned_sender_fallback():
    """When prev_owner is absent, source is used as sender."""
    msg = _msg(
        op_code=OP_NFT_OWNERSHIP_ASSIGNED,
        source="EQnft_item",
        destination="EQnew_owner",
    )
    result = decode_nft_transfer(_tx(), msg)
    assert result is not None
    assert result.sender == "EQnft_item"


# ---------------------------------------------------------------------------
# extract_nft_transfers
# ---------------------------------------------------------------------------


def test_extract_scans_in_message():
    nft_msg = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQsender",
        destination="EQnft_item",
        raw={"new_owner": "EQrecipient"},
    )

    class FakeTx:
        hash = "h1"
        in_message = nft_msg
        out_messages: tuple = ()

    results = extract_nft_transfers(FakeTx())  # type: ignore[arg-type]
    assert len(results) == 1
    assert results[0].sender == "EQsender"
    assert results[0].recipient == "EQrecipient"


def test_extract_skips_non_nft_messages():
    tx = _tx()
    non_nft = _msg(op_code=0xDEADBEEF, source="EQa", destination="EQb")

    # Inject message via extract by patching in_message via a simple wrapper
    class FakeTx:
        hash = tx.hash
        in_message = non_nft
        out_messages: tuple = ()

    results = extract_nft_transfers(FakeTx())  # type: ignore[arg-type]
    assert results == []


def test_extract_multiple_messages():
    """extract_nft_transfers finds transfers in both in and out messages."""
    msg1 = _msg(
        op_code=OP_NFT_TRANSFER,
        source="EQa",
        destination="EQnft1",
        raw={"new_owner": "EQb"},
    )
    msg2 = _msg(
        op_code=OP_NFT_OWNERSHIP_ASSIGNED,
        source="EQnft2",
        destination="EQc",
        raw={"prev_owner": "EQd"},
    )

    class FakeTx:
        hash = "txhash"
        in_message = msg1
        out_messages = (msg2,)

    results = extract_nft_transfers(FakeTx())  # type: ignore[arg-type]
    assert len(results) == 2
    assert results[0].nft_address == "EQnft1"
    assert results[1].nft_address == "EQnft2"
