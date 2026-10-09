"""DEX swap event decoding for Ston.fi and DeDust."""

from __future__ import annotations

from tonflow.models import DexName, DexSwap, Message, Transaction

# ---------------------------------------------------------------------------
# Ston.fi op codes (router v1)
# ---------------------------------------------------------------------------

# Sent as forward_payload in a Jetton transfer to the Ston.fi router — initiates a swap.
OP_STONFI_SWAP = 0x25938561

# Sent by the Ston.fi pool back to the router after a swap completes ("pay_to").
# Contains amount0_out / amount1_out — the actual amounts paid out.
OP_STONFI_PAY_TO = 0xF93BB43F

# ---------------------------------------------------------------------------
# DeDust op codes (v2)
# ---------------------------------------------------------------------------

# Sent directly to VaultNative with TON attached — initiates a TON→Jetton swap.
OP_DEDUST_SWAP_NATIVE = 0xEA06185D

# Sent as forward_payload in a Jetton transfer to VaultJetton — initiates a Jetton swap.
OP_DEDUST_SWAP_JETTON = 0xE3A0D482

# Emitted by the DeDust Pool contract as the swap result event.
OP_DEDUST_SWAP_POOL = 0x9C610DE3


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def is_stonfi_swap(message: Message) -> bool:
    """Return True if the message is a Ston.fi swap initiation or payout."""
    return message.op_code in (OP_STONFI_SWAP, OP_STONFI_PAY_TO)


def is_dedust_swap(message: Message) -> bool:
    """Return True if the message is a DeDust swap initiation or result."""
    return message.op_code in (OP_DEDUST_SWAP_NATIVE, OP_DEDUST_SWAP_JETTON, OP_DEDUST_SWAP_POOL)


def is_dex_swap(message: Message) -> bool:
    """Return True if the message belongs to any supported DEX swap flow."""
    return is_stonfi_swap(message) or is_dedust_swap(message)


# ---------------------------------------------------------------------------
# Ston.fi decoding
# ---------------------------------------------------------------------------


def decode_stonfi_swap(transaction: Transaction, message: Message) -> DexSwap | None:
    """Decode a Ston.fi swap message into a :class:`~tonflow.models.DexSwap`.

    Handles both message types:

    - ``0x25938561`` (swap request) — sent by the user's wallet to the Ston.fi
      router as the ``forward_payload`` of a Jetton transfer.  ``amount_in``
      comes from the enclosing Jetton transfer's ``amount`` field.
      ``amount_out`` is the ``min_out`` (minimum acceptable output).

    - ``0xf93bb43f`` (pay_to) — sent by the Ston.fi pool to the router after
      the swap completes.  ``amount_out`` is the total paid out
      (``amount0_out`` + ``amount1_out``).

    Returns ``None`` if the message op code is not a Ston.fi op.
    """
    if message.op_code not in (OP_STONFI_SWAP, OP_STONFI_PAY_TO):
        return None

    raw = message.raw

    if message.op_code == OP_STONFI_PAY_TO:
        # pay_to: pool → router.  Amounts are split across two output tokens.
        amount0 = _to_int(raw.get("amount0_out"))
        amount1 = _to_int(raw.get("amount1_out"))
        amount_out = amount0 + amount1
        receiver = _str(raw.get("owner")) or message.destination
        return DexSwap(
            transaction_hash=transaction.hash,
            dex=DexName.STONFI,
            sender=message.source,
            receiver=receiver,
            amount_in=0,  # not available in this message
            amount_out=amount_out,
            router=message.source,
            raw=dict(raw),
        )

    # swap request (0x25938561): user → router via Jetton transfer forward payload.
    amount_in = _to_int(raw.get("amount") or raw.get("jetton_amount"))
    amount_out = _to_int(raw.get("min_out"))
    sender = _str(raw.get("sender")) or message.source
    receiver = _str(raw.get("to_address")) or _str(raw.get("receiver")) or message.destination

    return DexSwap(
        transaction_hash=transaction.hash,
        dex=DexName.STONFI,
        sender=sender,
        receiver=receiver,
        amount_in=amount_in,
        amount_out=amount_out,
        router=message.destination,
        raw=dict(raw),
    )


# ---------------------------------------------------------------------------
# DeDust decoding
# ---------------------------------------------------------------------------


def decode_dedust_swap(transaction: Transaction, message: Message) -> DexSwap | None:
    """Decode a DeDust swap message into a :class:`~tonflow.models.DexSwap`.

    Handles three message types:

    - ``0xea06185d`` (VaultNative swap) — native TON sent to the DeDust
      VaultNative contract.  ``amount_in`` is ``message.value``.

    - ``0xe3a0d482`` (VaultJetton swap) — Jetton swap forwarded to the DeDust
      VaultJetton.  ``amount_in`` comes from the ``amount`` / ``jetton_amount``
      field in the forward payload.

    - ``0x9c610de3`` (Pool swap result) — external message emitted by the
      DeDust Pool after a swap.  ``amount0`` / ``amount1`` are the pool-side
      amounts involved.

    Returns ``None`` if the message op code is not a DeDust op.
    """
    if message.op_code not in (OP_DEDUST_SWAP_NATIVE, OP_DEDUST_SWAP_JETTON, OP_DEDUST_SWAP_POOL):
        return None

    raw = message.raw

    if message.op_code == OP_DEDUST_SWAP_POOL:
        # Pool result event.
        amount0 = _to_int(raw.get("amount0"))
        amount1 = _to_int(raw.get("amount1"))
        sender = _str(raw.get("sender")) or message.source
        jetton_in = _str(raw.get("asset0") or raw.get("jetton_master_in"))
        jetton_out = _str(raw.get("asset1") or raw.get("jetton_master_out"))
        return DexSwap(
            transaction_hash=transaction.hash,
            dex=DexName.DEDUST,
            sender=sender,
            receiver=_str(raw.get("receiver")) or message.destination,
            amount_in=amount0,
            amount_out=amount1,
            jetton_master_in=jetton_in,
            jetton_master_out=jetton_out,
            router=message.source,
            raw=dict(raw),
        )

    if message.op_code == OP_DEDUST_SWAP_NATIVE:
        # TON → Jetton swap via VaultNative.
        amount_in = _to_int(raw.get("amount")) or message.value or 0
        return DexSwap(
            transaction_hash=transaction.hash,
            dex=DexName.DEDUST,
            sender=_str(raw.get("sender")) or message.source,
            receiver=_str(raw.get("recipient")) or message.destination,
            amount_in=amount_in,
            amount_out=0,  # result comes in a separate pool event
            router=message.destination,
            raw=dict(raw),
        )

    # OP_DEDUST_SWAP_JETTON — Jetton → * swap via VaultJetton.
    amount_in = _to_int(raw.get("amount") or raw.get("jetton_amount"))
    jetton_in = _str(raw.get("jetton_master") or raw.get("jetton_master_in"))
    return DexSwap(
        transaction_hash=transaction.hash,
        dex=DexName.DEDUST,
        sender=_str(raw.get("sender")) or message.source,
        receiver=_str(raw.get("recipient")) or message.destination,
        amount_in=amount_in,
        amount_out=0,  # result comes in a separate pool event
        jetton_master_in=jetton_in,
        router=message.destination,
        raw=dict(raw),
    )


# ---------------------------------------------------------------------------
# Unified extract helper
# ---------------------------------------------------------------------------


def extract_dex_swaps(transaction: Transaction) -> list[DexSwap]:
    """Extract all DEX swap events from a transaction's messages.

    Scans the inbound message and all outbound messages. Returns one
    :class:`~tonflow.models.DexSwap` per recognized DEX message.

    Example::

        txs = await client.get_transactions("EQ...")
        for tx in txs:
            for swap in extract_dex_swaps(tx):
                print(swap.dex, swap.amount_in, swap.amount_out)
    """
    swaps: list[DexSwap] = []
    messages: list[Message] = []
    if transaction.in_message is not None:
        messages.append(transaction.in_message)
    messages.extend(transaction.out_messages)

    for msg in messages:
        result = decode_stonfi_swap(transaction, msg)
        if result is not None:
            swaps.append(result)
            continue
        result = decode_dedust_swap(transaction, msg)
        if result is not None:
            swaps.append(result)

    return swaps


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
