"""Tests for get_balance() in TonClient and provider fetch_balance()."""

from __future__ import annotations

import httpx
import pytest

from tonflow.client import TonClient
from tonflow.exceptions import TonflowDecodeError
from tonflow.providers import TonAPIProvider, TonCenterProvider, _extract_balance

# ---------------------------------------------------------------------------
# _extract_balance helper
# ---------------------------------------------------------------------------


def test_extract_balance_int():
    assert _extract_balance({"balance": 1_000_000_000}, key="balance") == 1_000_000_000


def test_extract_balance_string():
    assert _extract_balance({"balance": "500000000"}, key="balance") == 500_000_000


def test_extract_balance_result_key():
    assert _extract_balance({"result": "12345"}, key="result") == 12345


def test_extract_balance_missing_key_raises():
    with pytest.raises(TonflowDecodeError):
        _extract_balance({}, key="balance")


def test_extract_balance_invalid_value_raises():
    with pytest.raises(TonflowDecodeError):
        _extract_balance({"balance": "not_a_number"}, key="balance")


# ---------------------------------------------------------------------------
# TonAPIProvider.fetch_balance via mock transport
# ---------------------------------------------------------------------------


def _tonapi_transport(balance: int) -> httpx.MockTransport:
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"balance": str(balance)}).encode())

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_tonapi_fetch_balance():
    http = httpx.AsyncClient(transport=_tonapi_transport(9_876_000_000), base_url="https://x")
    provider = TonAPIProvider(endpoint="https://x", http_client=http)
    result = await provider.fetch_balance("EQA123")
    assert result == 9_876_000_000
    await provider.aclose()


# ---------------------------------------------------------------------------
# TonCenterProvider.fetch_balance via mock transport
# ---------------------------------------------------------------------------


def _toncenter_transport(balance: int) -> httpx.MockTransport:
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=json.dumps({"ok": True, "result": str(balance)}).encode()
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_toncenter_fetch_balance():
    http = httpx.AsyncClient(transport=_toncenter_transport(1_234_567_890), base_url="https://x")
    provider = TonCenterProvider(endpoint="https://x", http_client=http)
    result = await provider.fetch_balance("EQA123")
    assert result == 1_234_567_890
    await provider.aclose()


# ---------------------------------------------------------------------------
# TonClient.get_balance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_get_balance():
    from unittest.mock import AsyncMock, MagicMock

    client = TonClient.__new__(TonClient)
    client._provider = MagicMock()
    client._provider.fetch_balance = AsyncMock(return_value=5_000_000_000)

    result = await client.get_balance("EQA123")
    assert result == 5_000_000_000
    client._provider.fetch_balance.assert_awaited_once()
