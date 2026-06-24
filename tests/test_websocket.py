"""Tests for WebSocket-based transaction streaming."""

from __future__ import annotations

import json
import sys
import types
from collections.abc import AsyncIterator
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from tonflow import TonClient
from tonflow.websocket import stream_transactions_ws

ADDRESS = "EQ" + "A" * 46
TX_HASH = "deadbeef" * 8


def _make_http_client(lt: int = 100) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "transactions": [
                        {
                            "hash": TX_HASH,
                            "lt": str(lt),
                            "now": 1_700_000_000,
                            "success": True,
                            "in_msg": {
                                "source": "EQ" + "S" * 46,
                                "destination": ADDRESS,
                                "value": "1000",
                            },
                            "out_msgs": [],
                        }
                    ]
                },
            )
        ),
    )


class FakeWebSocket:
    """Minimal WebSocket fake that yields a preset sequence of messages."""

    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration:
            raise StopAsyncIteration from None

    async def __aenter__(self) -> FakeWebSocket:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ws_messages(lt: int = 100) -> list[str]:
    return [
        json.dumps({"id": 1, "result": "success"}),
        json.dumps({"method": "account_transaction", "result": {"lt": lt, "tx_hash": TX_HASH}}),
    ]


@contextmanager
def _fake_websockets(fake_ws: FakeWebSocket, capture_url: list[str] | None = None):  # type: ignore[return]
    """Inject a fake websockets module into sys.modules for the duration of the block."""
    mod = types.ModuleType("websockets")

    def connect(url: str, **_kwargs: object) -> FakeWebSocket:
        if capture_url is not None:
            capture_url.append(url)
        return fake_ws

    mod.connect = connect  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"websockets": mod}):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_transaction_on_notification() -> None:
    http_client = _make_http_client(lt=100)
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    fake_ws = FakeWebSocket(_ws_messages(lt=100))

    with _fake_websockets(fake_ws):
        results: list = []
        async for tx in stream_transactions_ws(client, ADDRESS):
            results.append(tx)

    assert len(results) == 1
    assert results[0].hash == TX_HASH
    assert results[0].logical_time == 100
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_sends_correct_subscription_message() -> None:
    http_client = _make_http_client(lt=200)
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    fake_ws = FakeWebSocket(_ws_messages(lt=200))

    with _fake_websockets(fake_ws):
        async for _ in stream_transactions_ws(client, ADDRESS):
            pass

    assert len(fake_ws.sent) == 1
    msg = json.loads(fake_ws.sent[0])
    assert msg["method"] == "subscribe_account"
    assert ADDRESS in msg["params"]["accounts"]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_appends_api_key_to_url() -> None:
    http_client = _make_http_client()
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    fake_ws = FakeWebSocket([json.dumps({"id": 1, "result": "success"})])
    captured_url: list[str] = []

    with _fake_websockets(fake_ws, capture_url=captured_url):
        async for _ in stream_transactions_ws(client, ADDRESS, api_key="secret"):
            pass

    assert len(captured_url) == 1
    assert "token=secret" in captured_url[0]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_no_api_key_url_unchanged() -> None:
    http_client = _make_http_client()
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    fake_ws = FakeWebSocket([json.dumps({"id": 1, "result": "success"})])
    captured_url: list[str] = []

    with _fake_websockets(fake_ws, capture_url=captured_url):
        async for _ in stream_transactions_ws(client, ADDRESS):
            pass

    assert "token" not in captured_url[0]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_skips_non_account_transaction_messages() -> None:
    http_client = _make_http_client(lt=50)
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    messages = [
        json.dumps({"id": 1, "result": "success"}),
        json.dumps({"method": "heartbeat", "result": {}}),
        json.dumps({"method": "account_transaction", "result": {"lt": 50, "tx_hash": TX_HASH}}),
    ]
    fake_ws = FakeWebSocket(messages)

    with _fake_websockets(fake_ws):
        results: list = []
        async for tx in stream_transactions_ws(client, ADDRESS):
            results.append(tx)

    assert len(results) == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_skips_notification_without_lt() -> None:
    http_client = _make_http_client()
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)
    messages = [
        json.dumps({"id": 1, "result": "success"}),
        json.dumps({"method": "account_transaction", "result": {"tx_hash": TX_HASH}}),
    ]
    fake_ws = FakeWebSocket(messages)

    with _fake_websockets(fake_ws):
        results: list = []
        async for tx in stream_transactions_ws(client, ADDRESS):
            results.append(tx)

    assert results == []
    await http_client.aclose()


@pytest.mark.asyncio
async def test_stream_raises_import_error_without_websockets() -> None:
    http_client = _make_http_client()
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    with (
        patch.dict(sys.modules, {"websockets": None}),  # type: ignore[dict-item]
        pytest.raises(ImportError, match="pip install tonflow\\[ws\\]"),
    ):
        async for _ in stream_transactions_ws(client, ADDRESS):
            pass

    await http_client.aclose()
