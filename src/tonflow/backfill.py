"""Backfill utility — paginate the full transaction history of an address."""

from __future__ import annotations

from collections.abc import AsyncIterator

from tonflow.addresses import normalize_address
from tonflow.client import TonClient, _parse_transaction
from tonflow.models import Transaction


async def backfill_transactions(
    client: TonClient,
    address: str,
    *,
    page_size: int = 100,
    stop_before_lt: int | None = None,
) -> AsyncIterator[Transaction]:
    """Yield every historical transaction for *address*, oldest last.

    Paginates backwards through the chain using ``before_lt`` until the
    provider returns an empty page (start of history) or a transaction's
    logical time falls at or below *stop_before_lt*.

    Bypasses the client cache so every page is always fetched fresh.

    Args:
        client: A configured :class:`TonClient` instance.
        address: TON account address to backfill.
        page_size: Number of transactions to fetch per API call (max 256).
        stop_before_lt: Stop when a transaction's logical time is at or below
            this value. Useful for incremental backfills.

    Yields:
        :class:`~tonflow.models.Transaction` objects newest-first (matching
        API order).

    Example::

        async for tx in backfill_transactions(client, "EQ...", page_size=100):
            print(tx.hash, tx.logical_time)
    """
    normalized = normalize_address(address)
    before_lt: int | None = None

    while True:
        raw_list = await client._provider.fetch_raw_transactions(
            normalized, limit=page_size, before_lt=before_lt
        )
        if not raw_list:
            break

        for raw in raw_list:
            tx = _parse_transaction(raw, account=normalized)

            if stop_before_lt is not None and tx.logical_time <= stop_before_lt:
                return

            yield tx

        # Advance cursor: next page starts just before the last tx in this page.
        last_lt_raw = raw_list[-1].get("lt")
        if last_lt_raw is None:
            break
        try:
            before_lt = int(last_lt_raw)
        except (TypeError, ValueError):
            break
