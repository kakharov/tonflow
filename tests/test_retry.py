"""Tests for auto-retry logic in providers."""

from __future__ import annotations

import json

import httpx
import pytest

from tonflow.exceptions import TonflowAPIError
from tonflow.providers import TonAPIProvider


def _transport_sequence(responses: list[tuple[int, dict]]) -> httpx.MockTransport:
    """Return a transport that yields responses in order."""
    calls = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = next(calls)
        return httpx.Response(status, content=json.dumps(body).encode())

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_retry_succeeds_after_429() -> None:
    transport = _transport_sequence(
        [
            (429, {"error": "rate limit"}),
            (200, {"balance": "1000000000"}),
        ]
    )
    http = httpx.AsyncClient(transport=transport, base_url="https://x")
    provider = TonAPIProvider(
        endpoint="https://x", http_client=http, retry_attempts=2, retry_backoff=0.0
    )
    result = await provider.fetch_balance("EQA123")
    assert result == 1_000_000_000
    await provider.aclose()


@pytest.mark.asyncio
async def test_retry_exhausted_raises() -> None:
    transport = _transport_sequence(
        [
            (503, {"error": "unavailable"}),
            (503, {"error": "unavailable"}),
            (503, {"error": "unavailable"}),
        ]
    )
    http = httpx.AsyncClient(transport=transport, base_url="https://x")
    provider = TonAPIProvider(
        endpoint="https://x", http_client=http, retry_attempts=3, retry_backoff=0.0
    )
    with pytest.raises(TonflowAPIError) as exc_info:
        await provider.fetch_balance("EQA123")
    assert exc_info.value.status_code == 503
    await provider.aclose()


@pytest.mark.asyncio
async def test_non_retryable_status_raises_immediately() -> None:
    transport = _transport_sequence([(404, {"error": "not found"})])
    http = httpx.AsyncClient(transport=transport, base_url="https://x")
    provider = TonAPIProvider(
        endpoint="https://x", http_client=http, retry_attempts=3, retry_backoff=0.0
    )
    with pytest.raises(TonflowAPIError) as exc_info:
        await provider.fetch_balance("EQA123")
    assert exc_info.value.status_code == 404
    await provider.aclose()
