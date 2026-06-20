"""Tests for pluggable provider adapters."""

from __future__ import annotations

import base64

import httpx
import pytest

from tonflow import TonCenterProvider, TonClient, TransactionStatus
from tonflow.exceptions import TonflowAPIError, TonflowDecodeError
from tonflow.providers import Provider, TonAPIProvider

# ---------------------------------------------------------------------------
# Provider protocol conformance
# ---------------------------------------------------------------------------


def test_tonapi_provider_satisfies_protocol() -> None:
    provider = TonAPIProvider(endpoint="https://tonapi.example")
    assert isinstance(provider, Provider)


def test_toncenter_provider_satisfies_protocol() -> None:
    provider = TonCenterProvider()
    assert isinstance(provider, Provider)


# ---------------------------------------------------------------------------
# TonCenterProvider: response normalization
# ---------------------------------------------------------------------------


def _toncenter_response(
    *,
    tx_hash: str = "tc-hash",
    lt: str = "100",
    utime: int = 1_700_000_000,
    in_msg_source: str = "EQ" + "S" * 46,
    in_msg_dest: str = "EQ" + "D" * 46,
    value: str = "1000000",
    body_text: str | None = None,
    fee: str = "5000",
) -> dict:
    in_msg: dict = {
        "source": in_msg_source,
        "destination": in_msg_dest,
        "value": value,
        "fwd_fee": "0",
        "ihr_fee": "0",
    }
    if body_text is not None:
        encoded = base64.b64encode(body_text.encode()).decode()
        in_msg["msg_data"] = {"@type": "msg.dataText", "text": encoded}

    return {
        "ok": True,
        "result": [
            {
                "utime": utime,
                "transaction_id": {"hash": tx_hash, "lt": lt},
                "fee": fee,
                "storage_fee": "0",
                "other_fee": "0",
                "in_msg": in_msg,
                "out_msgs": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_toncenter_provider_normalizes_transaction_id() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_toncenter_response(tx_hash="abc123", lt="42"))
        ),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    txs = await client.get_transactions("EQ" + "D" * 46)

    assert len(txs) == 1
    assert txs[0].hash == "abc123"
    assert txs[0].logical_time == 42
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_parses_utime_as_timestamp() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_toncenter_response(utime=1_700_000_000))
        ),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    txs = await client.get_transactions("EQ" + "D" * 46)

    assert txs[0].timestamp == 1_700_000_000
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_decodes_base64_body() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_toncenter_response(body_text="hello toncenter"))
        ),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    txs = await client.get_transactions("EQ" + "D" * 46)

    assert txs[0].in_message is not None
    assert txs[0].in_message.body == "hello toncenter"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_parses_fee() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_toncenter_response(fee="9999"))
        ),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    txs = await client.get_transactions("EQ" + "D" * 46)

    assert txs[0].total_fees == 9999
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_sends_api_key_as_query_param() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": []})

    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(handler),
    )
    provider = TonCenterProvider(
        endpoint="https://toncenter.example",
        api_key="my-secret-key",
        http_client=http_client,
    )
    client = TonClient(provider=provider)

    await client.get_transactions("EQ" + "D" * 46)

    assert seen[0].url.params["api_key"] == "my-secret-key"
    assert "Authorization" not in seen[0].headers
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_raises_api_error_on_bad_status() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(429, json={"ok": False})),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    with pytest.raises(TonflowAPIError) as exc_info:
        await client.get_transactions("EQ" + "D" * 46)

    assert exc_info.value.status_code == 429
    await http_client.aclose()


@pytest.mark.asyncio
async def test_toncenter_provider_raises_decode_error_for_invalid_result() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"ok": True, "result": {}})
        ),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    with pytest.raises(TonflowDecodeError, match="must be a list"):
        await client.get_transactions("EQ" + "D" * 46)

    await http_client.aclose()


# ---------------------------------------------------------------------------
# TonClient: provider= kwarg
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tonclient_accepts_explicit_provider() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://toncenter.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_toncenter_response())),
    )
    provider = TonCenterProvider(endpoint="https://toncenter.example", http_client=http_client)
    client = TonClient(provider=provider)

    txs = await client.get_transactions("EQ" + "D" * 46)

    assert len(txs) == 1
    assert txs[0].status == TransactionStatus.UNKNOWN
    await http_client.aclose()
