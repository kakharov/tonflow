"""Tests for the polling stream."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tonflow.models import Transaction, TransactionStatus
from tonflow.stream import watch_address


def _tx(lt: int) -> Transaction:
    return Transaction(
        hash=f"hash{lt:04d}",
        account="EQAddr",
        lt=lt,
        status=TransactionStatus.SUCCESS,
    )


def _mock_client(side_effects: list[list[Transaction]]) -> AsyncMock:
    client = AsyncMock()
    client.get_transactions = AsyncMock(side_effect=side_effects)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watch_yields_new_transactions_after_seed() -> None:
    seed = [_tx(100), _tx(90)]
    poll1 = [_tx(110), _tx(100), _tx(90)]

    client = _mock_client([seed, poll1])

    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        result = await stream.__anext__()

    assert result.logical_time == 110


@pytest.mark.asyncio
async def test_watch_skips_seen_transactions() -> None:
    seed = [_tx(100)]
    poll1 = [_tx(100)]  # same as seed — nothing new

    client = _mock_client([seed, poll1, [_tx(200), _tx(100)]])

    collected: list[Transaction] = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 1:
                break

    assert collected[0].logical_time == 200


@pytest.mark.asyncio
async def test_watch_yields_in_ascending_order() -> None:
    seed: list[Transaction] = []
    poll1 = [_tx(300), _tx(200), _tx(100)]  # API returns newest first

    client = _mock_client([seed, poll1])

    collected: list[Transaction] = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 3:
                break

    lts = [tx.logical_time for tx in collected]
    assert lts == sorted(lts)


@pytest.mark.asyncio
async def test_watch_empty_poll_does_not_yield() -> None:
    seed = [_tx(100)]
    poll1: list[Transaction] = []  # empty — nothing to yield
    poll2 = [_tx(200)]

    client = _mock_client([seed, poll1, poll2])

    collected: list[Transaction] = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 1:
                break

    assert collected[0].logical_time == 200


@pytest.mark.asyncio
async def test_watch_empty_seed_yields_all_on_first_poll() -> None:
    seed: list[Transaction] = []
    poll1 = [_tx(50), _tx(40)]

    client = _mock_client([seed, poll1])

    collected: list[Transaction] = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 2:
                break

    assert [tx.logical_time for tx in collected] == [40, 50]


@pytest.mark.asyncio
async def test_watch_updates_last_lt_across_polls() -> None:
    seed = [_tx(100)]
    poll1 = [_tx(200), _tx(100)]
    poll2 = [_tx(300), _tx(200)]

    client = _mock_client([seed, poll1, poll2])

    collected: list[Transaction] = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 2:
                break

    assert [tx.logical_time for tx in collected] == [200, 300]
