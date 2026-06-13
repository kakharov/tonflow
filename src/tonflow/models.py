"""Core data models returned by tonflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True, frozen=True)
class Message:
    """Normalized TON message."""

    source: str | None
    destination: str | None
    value: int | None = None
    body: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class Transaction:
    """Normalized TON transaction."""

    hash: str
    account: str
    logical_time: int
    timestamp: int | None = None
    in_message: Message | None = None
    out_messages: tuple[Message, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class JettonTransfer:
    """Normalized Jetton transfer event."""

    transaction_hash: str
    sender: str | None
    recipient: str | None
    amount: Decimal
    raw_amount: int
    decimals: int
    jetton_wallet: str | None = None
    jetton_minter: str | None = None
    symbol: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
