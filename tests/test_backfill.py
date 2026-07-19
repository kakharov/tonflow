"""Tests for backfill_transactions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tonflow.backfill import backfill_transactions
from tonflow.client import TonClient


def _raw(lt: int) -> dict:
    return {"hash": f"hash_{lt}", "lt": lt, "account": "EQA", "status": "success"}


def _make_client(*pages: list[dict]) -> TonClient:
    client = TonClient.__new__(TonClient)
    client._provider = MagicMock()
    client._provider.fetch_raw_transactions = AsyncMock(side_effect=[*pages, []])
    return client


@pytest.mark.asyncio
async def test_backfill_single_page():
    raws = [_raw(300), _raw(200), _raw(100)]
    client = _make_client(raws)

    result = [tx async for tx in backfill_transactions(client, "EQA")]
    assert [tx.logical_time for tx in result] == [300, 200, 100]


@pytest.mark.asyncio
async def test_backfill_multiple_pages():
    page1 = [_raw(300), _raw(200)]
    page2 = [_raw(100), _raw(50)]
    client = _make_client(page1, page2)

    result = [tx async for tx in backfill_transactions(client, "EQA", page_size=2)]
    assert [tx.logical_time for tx in result] == [300, 200, 100, 50]


@pytest.mark.asyncio
async def test_backfill_stop_before_lt():
    raws = [_raw(300), _raw(200), _raw(100), _raw(50)]
    client = _make_client(raws)

    result = [tx async for tx in backfill_transactions(client, "EQA", stop_before_lt=100)]
    assert [tx.logical_time for tx in result] == [300, 200]


@pytest.mark.asyncio
async def test_backfill_empty_address():
    client = _make_client([])

    result = [tx async for tx in backfill_transactions(client, "EQA")]
    assert result == []


@pytest.mark.asyncio
async def test_backfill_passes_before_lt_to_provider():
    page1 = [_raw(200), _raw(100)]
    client = _make_client(page1)

    _ = [tx async for tx in backfill_transactions(client, "EQA", page_size=2)]

    calls = client._provider.fetch_raw_transactions.call_args_list
    # First call: no before_lt
    assert calls[0].kwargs["before_lt"] is None
    # Second call: before_lt = last lt of previous page
    assert calls[1].kwargs["before_lt"] == 100


@pytest.mark.asyncio
async def test_backfill_uses_page_size():
    client = _make_client([])

    _ = [tx async for tx in backfill_transactions(client, "EQA", page_size=42)]

    calls = client._provider.fetch_raw_transactions.call_args_list
    assert calls[0].kwargs["limit"] == 42
