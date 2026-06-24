"""Core data models returned by tonflow."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RawPayload = dict[str, Any]


class TonflowModel(BaseModel):
    """Base model with stable serialization defaults."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class MessageDirection(StrEnum):
    """Direction of a message relative to the indexed account."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TransactionStatus(StrEnum):
    """Normalized transaction execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Message(TonflowModel):
    """Normalized TON message."""

    source: str | None
    destination: str | None
    direction: MessageDirection | None = None
    value: int | None = Field(default=None, ge=0)
    body: str | None = None
    op_code: int | None = Field(default=None, ge=0)
    raw: RawPayload = Field(default_factory=dict)


class Transaction(TonflowModel):
    """Normalized TON transaction."""

    hash: str
    account: str
    logical_time: int = Field(alias="lt", ge=0)
    timestamp: int | None = Field(default=None, ge=0)
    status: TransactionStatus = TransactionStatus.UNKNOWN
    in_message: Message | None = None
    out_messages: tuple[Message, ...] = ()
    total_fees: int | None = Field(default=None, ge=0)
    raw: RawPayload = Field(default_factory=dict)


class JettonTransfer(TonflowModel):
    """Normalized Jetton transfer event."""

    transaction_hash: str
    sender: str | None
    recipient: str | None
    amount: Decimal = Field(ge=0)
    raw_amount: int = Field(ge=0)
    decimals: int = Field(ge=0, le=255)
    jetton_wallet: str | None = None
    jetton_minter: str | None = None
    symbol: str | None = None
    comment: str | None = None
    raw: RawPayload = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class JettonBurn(TonflowModel):
    """Normalized Jetton burn event (TEP-74 op 0x595f07bc).

    Emitted when a token holder destroys tokens by sending a burn message
    from their Jetton wallet to the minter contract.
    """

    transaction_hash: str
    sender: str | None
    amount: Decimal = Field(ge=0)
    raw_amount: int = Field(ge=0)
    decimals: int = Field(ge=0, le=255)
    jetton_wallet: str | None = None
    jetton_minter: str | None = None
    symbol: str | None = None
    comment: str | None = None
    raw: RawPayload = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class JettonMint(TonflowModel):
    """Normalized Jetton mint event (TEP-74 internal_transfer op 0x178d4519).

    Emitted when the minter contract creates new tokens and sends them to
    a Jetton wallet via an internal_transfer message.
    """

    transaction_hash: str
    recipient: str | None
    amount: Decimal = Field(ge=0)
    raw_amount: int = Field(ge=0)
    decimals: int = Field(ge=0, le=255)
    jetton_wallet: str | None = None
    jetton_minter: str | None = None
    symbol: str | None = None
    raw: RawPayload = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
