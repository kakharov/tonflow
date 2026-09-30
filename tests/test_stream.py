"""Tests for the polling stream."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tonflow.stream import watch_address


def _raw(lt: int) -> dict:
    return {"hash": f"hash{lt:04d}", "lt": lt, "success": True}


def _mock_client(side_effects: list[list[dict]]) -> MagicMock:
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(side_effect=side_effects)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watch_yields_new_transactions_after_seed() -> None:
    seed = [_raw(100), _raw(90)]
    poll1 = [_raw(110), _raw(100), _raw(90)]

    client = _mock_client([seed, poll1])

    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        result = await stream.__anext__()

    assert result.logical_time == 110


@pytest.mark.asyncio
async def test_watch_skips_seen_transactions() -> None:
    seed = [_raw(100)]
    poll1 = [_raw(100)]  # same as seed — nothing new
    poll2 = [_raw(200), _raw(100)]

    client = _mock_client([seed, poll1, poll2])

    collected = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 1:
                break

    assert collected[0].logical_time == 200


@pytest.mark.asyncio
async def test_watch_yields_in_ascending_order() -> None:
    seed: list[dict] = []
    poll1 = [_raw(300), _raw(200), _raw(100)]

    client = _mock_client([seed, poll1])

    collected = []
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
    seed = [_raw(100)]
    poll1: list[dict] = []
    poll2 = [_raw(200)]

    client = _mock_client([seed, poll1, poll2])

    collected = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 1:
                break

    assert collected[0].logical_time == 200


@pytest.mark.asyncio
async def test_watch_empty_seed_yields_all_on_first_poll() -> None:
    seed: list[dict] = []
    poll1 = [_raw(50), _raw(40)]

    client = _mock_client([seed, poll1])

    collected = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 2:
                break

    assert [tx.logical_time for tx in collected] == [40, 50]


@pytest.mark.asyncio
async def test_watch_updates_last_lt_across_polls() -> None:
    seed = [_raw(100)]
    poll1 = [_raw(200), _raw(100)]
    poll2 = [_raw(300), _raw(200)]

    client = _mock_client([seed, poll1, poll2])

    collected = []
    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        async for tx in stream:
            collected.append(tx)
            if len(collected) >= 2:
                break

    assert [tx.logical_time for tx in collected] == [200, 300]


@pytest.mark.asyncio
async def test_watch_bypasses_cache() -> None:
    """Verify watch_address calls _provider directly, not client.get_transactions."""
    seed = [_raw(100)]
    poll1 = [_raw(200), _raw(100)]

    client = _mock_client([seed, poll1])

    with patch("tonflow.stream.asyncio.sleep", new_callable=AsyncMock):
        stream = watch_address(client, "EQAddr", interval_seconds=1)
        await stream.__anext__()

    assert client._provider.fetch_raw_transactions.await_count >= 1
    assert not hasattr(client, "get_transactions") or not client.get_transactions.called
