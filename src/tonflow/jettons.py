"""Jetton event normalization helpers."""

from decimal import Decimal

from tonflow.models import JettonBurn, JettonMint, JettonTransfer, Message, Transaction

# TEP-74 Jetton standard op codes
OP_JETTON_TRANSFER = 0xF8A7EA5
OP_JETTON_TRANSFER_NOTIFICATION = 0x7362D09C
OP_JETTON_INTERNAL_TRANSFER = 0x178D4519
OP_JETTON_BURN = 0x595F07BC
OP_JETTON_BURN_NOTIFICATION = 0x7BDD97DE


def normalize_amount(raw_amount: int | str, decimals: int) -> Decimal:
    """Convert a raw Jetton amount into a human-readable decimal value."""
    amount = Decimal(str(raw_amount))
    scale = Decimal(10) ** decimals
    return amount / scale


def is_jetton_transfer(message: Message) -> bool:
    """Return True if the message op_code matches a Jetton transfer."""
    return message.op_code == OP_JETTON_TRANSFER


def is_jetton_transfer_notification(message: Message) -> bool:
    """Return True if op_code matches a Jetton transfer notification."""
    return message.op_code == OP_JETTON_TRANSFER_NOTIFICATION


def is_jetton_burn(message: Message) -> bool:
    """Return True if op_code matches a Jetton burn."""
    return message.op_code == OP_JETTON_BURN


def decode_jetton_transfer(
    transaction: Transaction,
    message: Message,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> JettonTransfer | None:
    """Parse a Jetton transfer from a transaction message.

    Returns a JettonTransfer if the message is a recognized Jetton transfer,
    otherwise returns None.

    Supports both TEP-74 transfer (op 0xf8a7ea5) and transfer_notification
    (op 0x7362d09c). The raw payload is expected to carry the token amount
    under the key ``"amount"`` and optionally ``"comment"`` / ``"forward_payload"``.
    """
    if message.op_code not in (OP_JETTON_TRANSFER, OP_JETTON_TRANSFER_NOTIFICATION):
        return None

    raw = message.raw

    # Amount may come from the message value or an explicit ``amount`` field in
    # the decoded payload (TonAPI style).
    raw_amount_value = raw.get("amount") or raw.get("jetton_amount")
    if raw_amount_value is None:
        raw_amount_value = message.value or 0

    try:
        raw_amount = int(raw_amount_value)
    except (TypeError, ValueError):
        raw_amount = 0

    # Sender/recipient depend on message direction:
    # - transfer (0xf8a7ea5): sender = message.source (Jetton wallet owner)
    # - transfer_notification (0x7362d09c): recipient is the destination contract
    sender = raw.get("sender") or message.source
    recipient = raw.get("recipient") or raw.get("destination") or message.destination

    comment: str | None = None
    forward = raw.get("forward_payload") or raw.get("comment")
    if isinstance(forward, str) and forward:
        comment = forward

    return JettonTransfer(
        transaction_hash=transaction.hash,
        sender=sender,
        recipient=recipient,
        amount=normalize_amount(raw_amount, decimals),
        raw_amount=raw_amount,
        decimals=decimals,
        jetton_wallet=(
            message.destination if message.op_code == OP_JETTON_TRANSFER else message.source
        ),
        jetton_minter=jetton_minter,
        symbol=symbol,
        comment=comment,
        raw=dict(raw),
    )


def is_jetton_mint(message: Message) -> bool:
    """Return True if op_code matches a Jetton internal_transfer (mint from minter)."""
    return message.op_code == OP_JETTON_INTERNAL_TRANSFER


def decode_jetton_burn(
    transaction: Transaction,
    message: Message,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> JettonBurn | None:
    """Parse a Jetton burn event from a transaction message.

    Returns a JettonBurn if the message op_code is OP_JETTON_BURN (0x595f07bc),
    otherwise returns None.

    In TEP-74, a burn is initiated by the token holder: their Jetton wallet sends
    a burn message to the minter contract. The wallet is the message source and
    the minter is the destination.
    """
    if message.op_code != OP_JETTON_BURN:
        return None

    raw = message.raw
    raw_amount_value = raw.get("amount") or raw.get("jetton_amount")
    if raw_amount_value is None:
        raw_amount_value = message.value or 0

    try:
        raw_amount = int(raw_amount_value)
    except (TypeError, ValueError):
        raw_amount = 0

    comment: str | None = None
    forward = raw.get("custom_payload") or raw.get("comment")
    if isinstance(forward, str) and forward:
        comment = forward

    return JettonBurn(
        transaction_hash=transaction.hash,
        sender=raw.get("sender") or message.source,
        amount=normalize_amount(raw_amount, decimals),
        raw_amount=raw_amount,
        decimals=decimals,
        jetton_wallet=message.source,
        jetton_minter=jetton_minter or message.destination,
        symbol=symbol,
        comment=comment,
        raw=dict(raw),
    )


def decode_jetton_mint(
    transaction: Transaction,
    message: Message,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> JettonMint | None:
    """Parse a Jetton mint event from a transaction message.

    Returns a JettonMint if the message op_code is OP_JETTON_INTERNAL_TRANSFER
    (0x178d4519), otherwise returns None.

    In TEP-74, minting is done by sending an internal_transfer from the minter
    contract to the recipient's Jetton wallet. The minter is the message source
    and the wallet is the destination.
    """
    if message.op_code != OP_JETTON_INTERNAL_TRANSFER:
        return None

    raw = message.raw
    raw_amount_value = raw.get("amount") or raw.get("jetton_amount")
    if raw_amount_value is None:
        raw_amount_value = message.value or 0

    try:
        raw_amount = int(raw_amount_value)
    except (TypeError, ValueError):
        raw_amount = 0

    return JettonMint(
        transaction_hash=transaction.hash,
        recipient=raw.get("recipient") or message.destination,
        amount=normalize_amount(raw_amount, decimals),
        raw_amount=raw_amount,
        decimals=decimals,
        jetton_wallet=message.destination,
        jetton_minter=jetton_minter or message.source,
        symbol=symbol,
        raw=dict(raw),
    )


def extract_jetton_burns(
    transaction: Transaction,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> list[JettonBurn]:
    """Extract all Jetton burn events from a transaction's messages."""
    burns: list[JettonBurn] = []
    messages: list[Message] = []
    if transaction.in_message is not None:
        messages.append(transaction.in_message)
    messages.extend(transaction.out_messages)

    for msg in messages:
        result = decode_jetton_burn(
            transaction, msg, decimals=decimals, jetton_minter=jetton_minter, symbol=symbol
        )
        if result is not None:
            burns.append(result)
    return burns


def extract_jetton_mints(
    transaction: Transaction,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> list[JettonMint]:
    """Extract all Jetton mint events from a transaction's messages."""
    mints: list[JettonMint] = []
    messages: list[Message] = []
    if transaction.in_message is not None:
        messages.append(transaction.in_message)
    messages.extend(transaction.out_messages)

    for msg in messages:
        result = decode_jetton_mint(
            transaction, msg, decimals=decimals, jetton_minter=jetton_minter, symbol=symbol
        )
        if result is not None:
            mints.append(result)
    return mints


def extract_jetton_transfers(
    transaction: Transaction,
    *,
    decimals: int = 9,
    jetton_minter: str | None = None,
    symbol: str | None = None,
) -> list[JettonTransfer]:
    """Extract all Jetton transfers from a transaction's messages.

    Scans both the inbound message and all outbound messages.
    """
    transfers: list[JettonTransfer] = []

    messages: list[Message] = []
    if transaction.in_message is not None:
        messages.append(transaction.in_message)
    messages.extend(transaction.out_messages)

    for msg in messages:
        result = decode_jetton_transfer(
            transaction,
            msg,
            decimals=decimals,
            jetton_minter=jetton_minter,
            symbol=symbol,
        )
        if result is not None:
            transfers.append(result)

    return transfers
