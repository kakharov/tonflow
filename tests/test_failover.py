"""Tests for FailoverProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tonflow.exceptions import TonflowAPIError
from tonflow.providers import FailoverProvider


def _provider(balance: int | None = None, *, fail: bool = False) -> MagicMock:
    p = MagicMock()
    if fail:
        p.fetch_balance = AsyncMock(side_effect=TonflowAPIError("boom", status_code=503))
        p.fetch_raw_transactions = AsyncMock(side_effect=TonflowAPIError("boom", status_code=503))
        p.send_boc = AsyncMock(side_effect=TonflowAPIError("boom", status_code=503))
    else:
        p.fetch_balance = AsyncMock(return_value=balance)
        p.fetch_raw_transactions = AsyncMock(return_value=[])
        p.send_boc = AsyncMock(return_value=None)
    p.aclose = AsyncMock()
    return p


@pytest.mark.asyncio
async def test_failover_uses_primary_when_healthy() -> None:
    primary = _provider(balance=1_000)
    fallback = _provider(balance=2_000)
    fp = FailoverProvider(primary, fallback)

    result = await fp.fetch_balance("EQA123")
    assert result == 1_000
    primary.fetch_balance.assert_awaited_once()
    fallback.fetch_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_failover_switches_to_fallback_on_error() -> None:
    primary = _provider(fail=True)
    fallback = _provider(balance=5_000)
    fp = FailoverProvider(primary, fallback)

    result = await fp.fetch_balance("EQA123")
    assert result == 5_000
    fallback.fetch_balance.assert_awaited_once()


@pytest.mark.asyncio
async def test_failover_raises_if_fallback_also_fails() -> None:
    primary = _provider(fail=True)
    fallback = _provider(fail=True)
    fp = FailoverProvider(primary, fallback)

    with pytest.raises(TonflowAPIError):
        await fp.fetch_balance("EQA123")


@pytest.mark.asyncio
async def test_failover_aclose_closes_both() -> None:
    primary = _provider(balance=0)
    fallback = _provider(balance=0)
    fp = FailoverProvider(primary, fallback)

    await fp.aclose()
    primary.aclose.assert_awaited_once()
    fallback.aclose.assert_awaited_once()
