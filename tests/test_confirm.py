"""Tests for send_and_confirm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tonflow.confirm import send_and_confirm
from tonflow.exceptions import TonflowExpiredError, TonflowTimeoutError


def _raw_tx(logical_time: int) -> dict:
    """Minimal raw transaction payload as returned by a provider."""
    return {
        "hash": f"hash_{logical_time}",
        "lt": logical_time,
        "account": "EQA123",
        "utime": 1_700_000_000,
        "total_fees": "0",
        "status": "success",
    }


def _make_client(seed_raws: list[dict], poll_raws: list[dict]) -> MagicMock:
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(side_effect=[seed_raws, poll_raws])
    client._provider.send_boc = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_confirm_returns_new_transaction():
    """Returns first transaction newer than baseline."""
    client = _make_client([_raw_tx(100)], [_raw_tx(200), _raw_tx(100)])

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=30, poll_interval=1)

    assert tx.logical_time == 200
    client._provider.send_boc.assert_awaited_once_with("boc_data")


@pytest.mark.asyncio
async def test_confirm_no_baseline_accepts_any_tx():
    """When account has no prior transactions, any tx is confirmation."""
    client = _make_client([], [_raw_tx(50)])

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=30, poll_interval=1)

    assert tx.logical_time == 50


@pytest.mark.asyncio
async def test_confirm_timeout_raises():
    """TonflowTimeoutError raised after timeout expires."""
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(
        side_effect=[[_raw_tx(100)]] + [[_raw_tx(100)]] * 20
    )
    client._provider.send_boc = AsyncMock()

    with (
        patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()),
        patch("tonflow.confirm.time") as mock_time,
    ):
        mock_time.side_effect = [0, 0, 0, 999, 999]
        with pytest.raises(TonflowTimeoutError):
            await send_and_confirm(client, "EQA123", "boc_data", timeout=10, poll_interval=1)


@pytest.mark.asyncio
async def test_confirm_expired_raises():
    """TonflowExpiredError raised when valid_until is in the past."""
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(
        side_effect=[[_raw_tx(100)]] + [[_raw_tx(100)]] * 20
    )
    client._provider.send_boc = AsyncMock()

    with (
        patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()),
        patch("tonflow.confirm.time") as mock_time,
    ):
        mock_time.side_effect = [0, 0, 0, 100, 100]
        with pytest.raises(TonflowExpiredError):
            await send_and_confirm(
                client, "EQA123", "boc_data", timeout=60, poll_interval=1, valid_until=50
            )


@pytest.mark.asyncio
async def test_confirm_expired_check_before_timeout():
    """ExpiredError takes priority over TimeoutError."""
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(
        side_effect=[[_raw_tx(100)]] + [[_raw_tx(100)]] * 20
    )
    client._provider.send_boc = AsyncMock()

    with (
        patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()),
        patch("tonflow.confirm.time") as mock_time,
    ):
        mock_time.side_effect = [0, 0, 0, 999, 999]
        with pytest.raises(TonflowExpiredError):
            await send_and_confirm(
                client, "EQA123", "boc_data", timeout=10, poll_interval=1, valid_until=50
            )


@pytest.mark.asyncio
async def test_confirm_address_normalized():
    """Address is normalized before calling provider."""
    client = _make_client([_raw_tx(100)], [_raw_tx(200)])

    with (
        patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()),
        patch("tonflow.confirm.normalize_address", return_value="EQ_NORMALIZED") as mock_norm,
    ):
        await send_and_confirm(client, "raw_address", "boc_data", timeout=30, poll_interval=1)

    mock_norm.assert_called_once_with("raw_address")
    for call in client._provider.fetch_raw_transactions.call_args_list:
        assert call.args[0] == "EQ_NORMALIZED"


@pytest.mark.asyncio
async def test_confirm_polls_multiple_times():
    """Keeps polling until a new transaction appears."""
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(
        side_effect=[
            [_raw_tx(100)],
            [_raw_tx(100)],
            [_raw_tx(100)],
            [_raw_tx(200)],
        ]
    )
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=60, poll_interval=1)

    assert tx.logical_time == 200
    assert client._provider.fetch_raw_transactions.await_count == 4  # 1 seed + 3 polls


@pytest.mark.asyncio
async def test_confirm_bypasses_cache():
    """send_and_confirm must not use client.get_transactions (which caches)."""
    client = _make_client([_raw_tx(100)], [_raw_tx(200)])

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        await send_and_confirm(client, "EQA123", "boc_data", timeout=30, poll_interval=1)

    # get_transactions (the caching path) must never be called
    assert not hasattr(client, "get_transactions") or not client.get_transactions.called


@pytest.mark.asyncio
async def test_confirm_send_boc_called_once():
    """BOC is broadcast exactly once regardless of poll count."""
    client = MagicMock()
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(
        side_effect=[[_raw_tx(100)], [_raw_tx(100)], [_raw_tx(200)]]
    )
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        await send_and_confirm(client, "EQA123", "boc_data", timeout=60, poll_interval=1)

    client._provider.send_boc.assert_awaited_once_with("boc_data")
