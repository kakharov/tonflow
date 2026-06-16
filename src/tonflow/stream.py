"""Polling-based streaming of new TON transactions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from tonflow.client import TonClient
from tonflow.models import Transaction


async def watch_address(
    client: TonClient,
    address: str,
    *,
    interval_seconds: float = 5.0,
    lookback: int = 10,
) -> AsyncIterator[Transaction]:
    """Yield new transactions for *address* as they appear on-chain.

    Polls ``client.get_transactions()`` every *interval_seconds* seconds.
    On the first call fetches the last *lookback* transactions to establish
    a baseline; subsequent polls only yield transactions with a logical time
    greater than the highest seen so far, so duplicates are never emitted.

    ``watch_address`` runs indefinitely. To stop it after a fixed duration or
    on an external signal, wrap it with :func:`asyncio.timeout` or cancel the
    enclosing task:

    .. code-block:: python

        import asyncio
        from tonflow import TonClient, watch_address

        async def main() -> None:
            async with TonClient(endpoint="https://tonapi.io") as client:
                # Stop automatically after 60 seconds
                async with asyncio.timeout(60):
                    async for tx in watch_address(client, "EQ..."):
                        print(tx.hash)

    Args:
        client: A configured :class:`TonClient` instance.
        address: The TON address to watch.
        interval_seconds: Seconds to wait between polls.
        lookback: Number of recent transactions to fetch on the first poll
            (used to seed the last-seen logical time without yielding old txs).

    Yields:
        :class:`Transaction` objects in ascending logical-time order.
    """
    last_lt: int | None = None

    # Seed: fetch recent transactions to set the baseline lt without yielding them.
    seed = await client.get_transactions(address, limit=lookback)
    if seed:
        last_lt = max(tx.logical_time for tx in seed)

    while True:
        await asyncio.sleep(interval_seconds)

        txs = await client.get_transactions(address, limit=lookback)
        if not txs:
            continue

        new_txs = [tx for tx in txs if last_lt is None or tx.logical_time > last_lt]
        if not new_txs:
            continue

        # Yield in ascending order (oldest first).
        new_txs.sort(key=lambda tx: tx.logical_time)
        for tx in new_txs:
            yield tx

        last_lt = max(tx.logical_time for tx in new_txs)
