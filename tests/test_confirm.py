"""Tests for send_and_confirm."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tonflow.confirm import send_and_confirm
from tonflow.exceptions import TonflowExpiredError, TonflowTimeoutError
from tonflow.models import Transaction


def _make_tx(logical_time: int) -> Transaction:
    return Transaction.model_validate(
        {
            "hash": f"hash_{logical_time}",
            "lt": logical_time,
            "account": "EQA123",
            "utime": 1_700_000_000,
            "total_fees": "0",
            "status": "success",
        }
    )


def _make_client(seed_txs: list[Transaction], poll_txs: list[Transaction]) -> MagicMock:
    client = MagicMock()
    client.get_transactions = AsyncMock(side_effect=[seed_txs, poll_txs])
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_confirm_returns_new_transaction():
    """Returns first transaction newer than baseline."""
    seed = [_make_tx(100)]
    poll = [_make_tx(200), _make_tx(100)]

    client = _make_client(seed, poll)

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=30, poll_interval=1)

    assert tx.logical_time == 200
    client._provider.send_boc.assert_awaited_once_with("boc_data")


@pytest.mark.asyncio
async def test_confirm_no_baseline_accepts_any_tx():
    """When account has no prior transactions, any tx is confirmation."""
    client = _make_client([], [_make_tx(50)])

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=30, poll_interval=1)

    assert tx.logical_time == 50


@pytest.mark.asyncio
async def test_confirm_timeout_raises():
    """TonflowTimeoutError raised after timeout expires."""
    seed = [_make_tx(100)]
    # poll returns only old tx → never confirms
    client = MagicMock()
    client.get_transactions = AsyncMock(side_effect=[seed] + [[_make_tx(100)]] * 20)
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        with patch("tonflow.confirm.time") as mock_time:
            # time() sequence: deadline=start+timeout, then increments past deadline
            mock_time.side_effect = [0, 0, 0, 999, 999]
            with pytest.raises(TonflowTimeoutError):
                await send_and_confirm(client, "EQA123", "boc_data", timeout=10, poll_interval=1)


@pytest.mark.asyncio
async def test_confirm_expired_raises():
    """TonflowExpiredError raised when valid_until is in the past."""
    seed = [_make_tx(100)]
    client = MagicMock()
    client.get_transactions = AsyncMock(side_effect=[seed] + [[_make_tx(100)]] * 20)
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        with patch("tonflow.confirm.time") as mock_time:
            # valid_until = 50, time() returns 100 (already past)
            mock_time.side_effect = [0, 0, 0, 100, 100]
            with pytest.raises(TonflowExpiredError):
                await send_and_confirm(
                    client, "EQA123", "boc_data", timeout=60, poll_interval=1, valid_until=50
                )


@pytest.mark.asyncio
async def test_confirm_expired_check_before_timeout():
    """ExpiredError takes priority over TimeoutError."""
    seed = [_make_tx(100)]
    client = MagicMock()
    client.get_transactions = AsyncMock(side_effect=[seed] + [[_make_tx(100)]] * 20)
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        with patch("tonflow.confirm.time") as mock_time:
            # Both deadline and valid_until passed; valid_until checked first
            mock_time.side_effect = [0, 0, 0, 999, 999]
            with pytest.raises(TonflowExpiredError):
                await send_and_confirm(
                    client, "EQA123", "boc_data", timeout=10, poll_interval=1, valid_until=50
                )


@pytest.mark.asyncio
async def test_confirm_address_normalized():
    """Address is normalized before fetching."""
    seed = [_make_tx(100)]
    poll = [_make_tx(200)]
    client = _make_client(seed, poll)

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        with patch("tonflow.confirm.normalize_address", return_value="EQ_NORMALIZED") as mock_norm:
            await send_and_confirm(client, "raw_address", "boc_data", timeout=30, poll_interval=1)

    mock_norm.assert_called_once_with("raw_address")
    # both get_transactions calls use the normalized address
    for call in client.get_transactions.call_args_list:
        assert call.args[0] == "EQ_NORMALIZED"


@pytest.mark.asyncio
async def test_confirm_polls_multiple_times():
    """Keeps polling until a new transaction appears."""
    seed = [_make_tx(100)]
    # first two polls return nothing new, third returns confirmation
    client = MagicMock()
    client.get_transactions = AsyncMock(
        side_effect=[seed, [_make_tx(100)], [_make_tx(100)], [_make_tx(200)]]
    )
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        tx = await send_and_confirm(client, "EQA123", "boc_data", timeout=60, poll_interval=1)

    assert tx.logical_time == 200
    assert client.get_transactions.await_count == 4  # 1 seed + 3 polls


@pytest.mark.asyncio
async def test_confirm_send_boc_called_once():
    """BOC is broadcast exactly once regardless of poll count."""
    seed = [_make_tx(100)]
    client = MagicMock()
    client.get_transactions = AsyncMock(side_effect=[seed, [_make_tx(100)], [_make_tx(200)]])
    client._provider = MagicMock()
    client._provider.send_boc = AsyncMock()

    with patch("tonflow.confirm.asyncio.sleep", new=AsyncMock()):
        await send_and_confirm(client, "EQA123", "boc_data", timeout=60, poll_interval=1)

    client._provider.send_boc.assert_awaited_once_with("boc_data")
