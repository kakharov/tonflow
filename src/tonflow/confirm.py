"""Send-and-confirm: broadcast a TON external message and wait for on-chain confirmation."""

from __future__ import annotations

import asyncio
from time import time

from tonflow.addresses import normalize_address
from tonflow.client import TonClient, _parse_transaction
from tonflow.exceptions import TonflowExpiredError, TonflowTimeoutError
from tonflow.models import Transaction


async def send_and_confirm(
    client: TonClient,
    address: str,
    boc: str,
    *,
    timeout: float = 60.0,
    poll_interval: float = 3.0,
    valid_until: int | None = None,
) -> Transaction:
    """Broadcast a signed external message and wait for on-chain confirmation.

    TON is fully asynchronous — sending a message does not guarantee execution.
    This function solves the confirmation problem by:

    1. Recording the account's latest logical time (baseline).
    2. Broadcasting the pre-built, pre-signed ``boc`` to the network.
    3. Polling :meth:`~tonflow.client.TonClient.get_transactions` every
       ``poll_interval`` seconds until a new transaction appears.
    4. Returning the first transaction whose logical time exceeds the baseline.

    Args:
        client: A configured :class:`TonClient` instance.
        address: The wallet address that signed and sent the message.
        boc: Base64-encoded Bag of Cells (the external message). Build this
            with a wallet library such as ``pytoniq`` or ``tonsdk``.
        timeout: Maximum seconds to wait for confirmation before raising
            :class:`~tonflow.exceptions.TonflowTimeoutError`.
        poll_interval: Seconds between each polling attempt.
        valid_until: Unix timestamp (seconds) after which the message will
            never be included in a block. When this deadline passes without
            confirmation, :class:`~tonflow.exceptions.TonflowExpiredError`
            is raised immediately instead of continuing to poll.

    Returns:
        The confirmed :class:`~tonflow.models.Transaction`.

    Raises:
        TonflowTimeoutError: ``timeout`` seconds elapsed without confirmation.
        TonflowExpiredError: ``valid_until`` passed before the transaction
            landed. The message is permanently rejected by the network — build
            a new message with an updated ``seqno`` and ``valid_until`` before
            retrying.

    Example::

        # boc is built externally with a wallet library
        tx = await send_and_confirm(
            client,
            wallet_address,
            boc,
            timeout=60,
            valid_until=int(time.time()) + 60,
        )
        print("confirmed:", tx.hash, tx.logical_time)
    """
    normalized = normalize_address(address)

    async def _fetch(limit: int, before_lt: int | None = None) -> list[Transaction]:
        # Bypass client cache — we need fresh data on every poll.
        raw_list = await client._provider.fetch_raw_transactions(
            normalized, limit=limit, before_lt=before_lt
        )
        return [_parse_transaction(item, account=normalized) for item in raw_list]

    # Step 1 — establish baseline: highest LT seen before we send.
    seed = await _fetch(1)
    baseline_lt: int | None = seed[0].logical_time if seed else None

    # Step 2 — broadcast.
    await client._provider.send_boc(boc)

    # Step 3 — poll until a new transaction appears or we time out.
    deadline = time() + timeout

    while True:
        await asyncio.sleep(poll_interval)

        # Check valid_until before fetching — if expired the tx will never land.
        if valid_until is not None and time() > valid_until:
            raise TonflowExpiredError(
                f"Transaction expired (valid_until={valid_until}). "
                "Build a new message with an updated seqno and valid_until before retrying."
            )

        if time() > deadline:
            raise TonflowTimeoutError(
                f"Transaction not confirmed within {timeout}s. "
                "The message may still land later — check the address manually."
            )

        txs = await _fetch(5)
        for tx in txs:
            if baseline_lt is None or tx.logical_time > baseline_lt:
                return tx
