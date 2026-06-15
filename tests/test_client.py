from __future__ import annotations

import httpx
import pytest

from tonflow import InMemoryCache, MessageDirection, TonClient, TransactionStatus
from tonflow.exceptions import TonflowAPIError, TonflowDecodeError


@pytest.mark.asyncio
async def test_get_transactions_fetches_and_normalizes_response() -> None:
    seen_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "transactions": [
                    {
                        "hash": "tx-hash",
                        "lt": "123",
                        "now": 1_700_000_000,
                        "success": True,
                        "total_fees": "42",
                        "in_msg": {
                            "source": "EQ" + "A" * 46,
                            "destination": "EQ" + "B" * 46,
                            "value": "1000",
                            "op_code": 0,
                        },
                        "out_msgs": [
                            {
                                "source": "EQ" + "B" * 46,
                                "destination": "EQ" + "C" * 46,
                                "value": 500,
                                "decoded_body": {"text": "hello"},
                            }
                        ],
                    }
                ]
            },
        )

    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    transactions = await client.get_transactions("EQ" + "B" * 46, limit=5, before_lt=200)

    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.hash == "tx-hash"
    assert transaction.logical_time == 123
    assert transaction.status == TransactionStatus.SUCCESS
    assert transaction.total_fees == 42
    assert transaction.in_message is not None
    assert transaction.in_message.direction == MessageDirection.INBOUND
    assert transaction.out_messages[0].body == "hello"
    assert seen_requests[0].url.path == "/v2/blockchain/accounts/EQ" + "B" * 46 + "/transactions"
    assert seen_requests[0].url.params["limit"] == "5"
    assert seen_requests[0].url.params["before_lt"] == "200"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_transactions_raises_api_error_on_bad_status() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, json={})),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    with pytest.raises(TonflowAPIError) as exc_info:
        await client.get_transactions("EQ" + "A" * 46)

    assert exc_info.value.status_code == 429
    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_transactions_raises_decode_error_for_invalid_payload() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"transactions": {}})
        ),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    with pytest.raises(TonflowDecodeError, match="must be a list"):
        await client.get_transactions("EQ" + "A" * 46)

    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_transactions_uses_cache_for_repeated_reads() -> None:
    request_count = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "transactions": [
                    {
                        "hash": "cached-tx",
                        "lt": 1,
                    }
                ]
            },
        )

    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(handler),
    )
    client = TonClient(
        endpoint="https://tonapi.example",
        http_client=http_client,
        cache=InMemoryCache(),
        cache_ttl_seconds=30,
    )

    first = await client.get_transactions("EQ" + "A" * 46, limit=1)
    second = await client.get_transactions("EQ" + "A" * 46, limit=1)

    assert first[0].hash == "cached-tx"
    assert second[0].hash == "cached-tx"
    assert request_count == 1
    await http_client.aclose()
