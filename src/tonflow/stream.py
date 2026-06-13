"""Streaming helpers for polling TON data sources."""

from collections.abc import AsyncIterator

from tonflow.client import TonClient
from tonflow.models import Transaction


async def watch_address(
    client: TonClient,
    address: str,
    *,
    interval_seconds: float = 5.0,
) -> AsyncIterator[Transaction]:
    """Yield new transactions for an address.

    This is a placeholder for the polling stream implementation planned after
    the first concrete transaction endpoint is added.
    """

    _ = (client, address, interval_seconds)
    if False:  # pragma: no cover
        yield
