"""NFT event normalization helpers (TEP-62)."""

from tonflow.models import Message, NftTransfer, Transaction

# TEP-62 NFT standard op codes
OP_NFT_TRANSFER = 0x5FCC3D14
OP_NFT_OWNERSHIP_ASSIGNED = 0x05138D91


def is_nft_transfer(message: Message) -> bool:
    """Return True if the message op_code matches an NFT transfer (TEP-62)."""
    return message.op_code == OP_NFT_TRANSFER


def is_nft_ownership_assigned(message: Message) -> bool:
    """Return True if op_code matches an NFT ownership_assigned notification."""
    return message.op_code == OP_NFT_OWNERSHIP_ASSIGNED


def decode_nft_transfer(
    transaction: Transaction,
    message: Message,
    *,
    nft_collection: str | None = None,
) -> NftTransfer | None:
    """Parse an NFT transfer event from a transaction message.

    Handles both TEP-62 op codes:
    - ``transfer`` (0x5fcc3d14): sent by the current owner to the NFT item contract.
      The sender is ``message.source``; the new owner is in ``raw["new_owner"]``
      or falls back to ``message.destination``.
    - ``ownership_assigned`` (0x05138d91): sent by the NFT item to the new owner.
      The previous owner is in ``raw["prev_owner"]`` or ``message.source``;
      the new owner is ``message.destination``.

    Returns None if the message is not a recognised NFT event.
    """
    if message.op_code not in (OP_NFT_TRANSFER, OP_NFT_OWNERSHIP_ASSIGNED):
        return None

    raw = message.raw

    if message.op_code == OP_NFT_TRANSFER:
        sender = raw.get("sender") or message.source
        recipient = raw.get("new_owner") or raw.get("recipient") or message.destination
        nft_address = message.destination
    else:
        # ownership_assigned: NFT item notifies new owner
        sender = raw.get("prev_owner") or message.source
        recipient = message.destination
        nft_address = message.source

    comment: str | None = None
    forward = raw.get("forward_payload") or raw.get("comment")
    if isinstance(forward, str) and forward:
        comment = forward

    return NftTransfer(
        transaction_hash=transaction.hash,
        sender=sender,
        recipient=recipient,
        nft_address=nft_address,
        nft_collection=nft_collection or raw.get("nft_collection"),
        comment=comment,
        raw=dict(raw),
    )


def extract_nft_transfers(
    transaction: Transaction,
    *,
    nft_collection: str | None = None,
) -> list[NftTransfer]:
    """Extract all NFT transfer events from a transaction's messages.

    Scans both the inbound message and all outbound messages.
    """
    transfers: list[NftTransfer] = []

    messages: list[Message] = []
    if transaction.in_message is not None:
        messages.append(transaction.in_message)
    messages.extend(transaction.out_messages)

    for msg in messages:
        result = decode_nft_transfer(transaction, msg, nft_collection=nft_collection)
        if result is not None:
            transfers.append(result)

    return transfers
