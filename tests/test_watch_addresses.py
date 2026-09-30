"""Tests for watch_addresses multi-address polling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tonflow.models import Transaction, TransactionStatus
from tonflow.stream import watch_addresses


def _tx(address: str, lt: int) -> Transaction:
    return Transaction(
        hash=f"{address[:4]}-{lt}",
        account=address,
        lt=lt,
        status=TransactionStatus.SUCCESS,
    )


@pytest.mark.asyncio
async def test_watch_addresses_merges_from_multiple() -> None:
    addr1 = "EQ" + "A" * 46
    addr2 = "EQ" + "B" * 46

    async def _fake_watch(client, address, *, interval_seconds=5.0, lookback=10):
        if address == addr1:
            yield _tx(addr1, 100)
        else:
            yield _tx(addr2, 200)

    results: list[Transaction] = []
    with patch("tonflow.stream.watch_address", side_effect=_fake_watch):
        async with asyncio.timeout(2):
            try:
                async for tx in watch_addresses(MagicMock(), [addr1, addr2]):
                    results.append(tx)
                    if len(results) == 2:
                        break
            except asyncio.TimeoutError:
                pass

    accounts = {tx.account for tx in results}
    assert addr1 in accounts
    assert addr2 in accounts


@pytest.mark.asyncio
async def test_watch_addresses_empty_list_returns_immediately() -> None:
    results = []
    async for tx in watch_addresses(MagicMock(), []):
        results.append(tx)
    assert results == []
