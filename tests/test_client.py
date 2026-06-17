from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from tonflow import InMemoryCache, MessageDirection, TonClient, TransactionStatus
from tonflow.exceptions import TonflowAPIError, TonflowDecodeError
from tonflow.jettons import OP_JETTON_TRANSFER, OP_JETTON_TRANSFER_NOTIFICATION


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


# ---------------------------------------------------------------------------
# get_jetton_transfers
# ---------------------------------------------------------------------------

SENDER = "EQ" + "S" * 46
WALLET = "EQ" + "W" * 46


def _jetton_tx_payload(amount: int = 1_000_000_000, op_code: int = OP_JETTON_TRANSFER) -> dict:
    return {
        "transactions": [
            {
                "hash": "jetton-tx-hash",
                "lt": "500",
                "now": 1_700_000_000,
                "success": True,
                "in_msg": {
                    "source": SENDER,
                    "destination": WALLET,
                    "value": str(amount),
                    "op_code": op_code,
                    "amount": str(amount),
                },
                "out_msgs": [],
            }
        ]
    }


@pytest.mark.asyncio
async def test_get_jetton_transfers_returns_decoded_transfers() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_jetton_tx_payload(2_000_000_000))
        ),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    transfers = await client.get_jetton_transfers(WALLET, decimals=9, symbol="USDT")

    assert len(transfers) == 1
    assert transfers[0].transaction_hash == "jetton-tx-hash"
    assert transfers[0].amount == Decimal("2")
    assert transfers[0].symbol == "USDT"
    assert transfers[0].sender == SENDER
    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_jetton_transfers_skips_non_jetton_transactions() -> None:
    payload = {
        "transactions": [
            {
                "hash": "plain-tx",
                "lt": "10",
                "in_msg": {
                    "source": SENDER,
                    "destination": WALLET,
                    "value": "1000",
                    "op_code": 0x0,
                },
                "out_msgs": [],
            }
        ]
    }
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    transfers = await client.get_jetton_transfers(WALLET)

    assert transfers == []
    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_jetton_transfers_handles_notification_op() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=_jetton_tx_payload(500_000_000, op_code=OP_JETTON_TRANSFER_NOTIFICATION)
            )
        ),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    transfers = await client.get_jetton_transfers(WALLET, decimals=9)

    assert len(transfers) == 1
    assert transfers[0].amount == Decimal("0.5")
    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_jetton_transfers_attaches_minter() -> None:
    MINTER = "EQ" + "M" * 46
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_jetton_tx_payload())),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    transfers = await client.get_jetton_transfers(WALLET, jetton_minter=MINTER)

    assert transfers[0].jetton_minter == MINTER
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


@pytest.mark.asyncio
async def test_get_transactions_handles_float_fees() -> None:
    """TonAPI sometimes returns integer fields as floats like 1234.0."""
    http_client = httpx.AsyncClient(
        base_url="https://tonapi.example",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "transactions": [
                        {
                            "hash": "float-tx",
                            "lt": 999,
                            "total_fees": 1234.0,  # float from API
                            "now": 1700000000.0,  # float timestamp
                        }
                    ]
                },
            )
        ),
    )
    client = TonClient(endpoint="https://tonapi.example", http_client=http_client)

    txs = await client.get_transactions("EQ" + "A" * 46)
    assert txs[0].total_fees == 1234
    assert txs[0].timestamp == 1700000000
    await http_client.aclose()
