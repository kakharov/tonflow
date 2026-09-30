"""Polling-based streaming of new TON transactions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from tonflow.addresses import normalize_address
from tonflow.client import TonClient, _parse_transaction
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
    normalized = normalize_address(address)

    async def _fetch(limit: int) -> list[Transaction]:
        # Bypass the client cache so every poll sees the latest chain state.
        raw_list = await client._provider.fetch_raw_transactions(
            normalized, limit=limit, before_lt=None
        )
        return [_parse_transaction(item, account=normalized) for item in raw_list]

    # Seed: fetch recent transactions to set the baseline lt without yielding them.
    seed = await _fetch(lookback)
    if seed:
        last_lt = max(tx.logical_time for tx in seed)

    while True:
        await asyncio.sleep(interval_seconds)

        txs = await _fetch(lookback)
        if not txs:
            continue

        new_txs = [tx for tx in txs if last_lt is None or tx.logical_time > last_lt]
        if not new_txs:
            continue

        new_txs.sort(key=lambda tx: tx.logical_time)
        for tx in new_txs:
            yield tx

        last_lt = max(tx.logical_time for tx in new_txs)


async def watch_addresses(
    client: TonClient,
    addresses: list[str],
    *,
    interval_seconds: float = 5.0,
    lookback: int = 10,
) -> AsyncIterator[Transaction]:
    """Watch multiple addresses concurrently, merging events into one stream.

    Internally runs one :func:`watch_address` coroutine per address in
    parallel; events from all addresses are merged into a single async
    iterator as they arrive.  The order across addresses is
    arrival-time order (not logical-time order), but each individual address
    still yields its own transactions in ascending logical-time order.

    Args:
        client: A configured :class:`TonClient` instance.
        addresses: List of TON addresses to watch.
        interval_seconds: Seconds between polls for each address.
        lookback: Lookback window passed to each :func:`watch_address`.

    Yields:
        :class:`Transaction` objects from any of the watched addresses.

    Example::

        async with TonClient() as client:
            async for tx in watch_addresses(client, ["EQ...", "UQ..."]):
                print(tx.account, tx.hash)
    """
    if not addresses:
        return

    queue: asyncio.Queue[Transaction] = asyncio.Queue()

    async def _drain(addr: str) -> None:
        async for tx in watch_address(
            client, addr, interval_seconds=interval_seconds, lookback=lookback
        ):
            await queue.put(tx)

    tasks = [asyncio.create_task(_drain(addr)) for addr in addresses]
    try:
        while True:
            yield await queue.get()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
