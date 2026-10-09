"""Tests for TonClient.resolve_domain."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tonflow.client import TonClient
from tonflow.exceptions import TonflowDecodeError

_DNS_PAYLOAD = {
    "name": "foundation.ton",
    "expiring_at": 1796149277,
    "item": {
        "address": "0:78dfe54299fd7b3bb60c779d5f02f3a370c902c38e8dff724c0a87a01ff643a3",
        "owner": {
            "address": "0:9da971000000000000000000000000000000000000000000000000000000001",
            "name": "tolya.ton",
        },
        "collection": {
            "address": "0:b774000000000000000000000000000000000000000000000000000000000001",
            "name": "TON DNS Domains",
        },
        "metadata": {"name": "foundation.ton"},
        "dns": "foundation.ton",
    },
}


@pytest.fixture()
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.fetch_dns_resolve = AsyncMock(return_value=_DNS_PAYLOAD)
    provider.aclose = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_resolve_domain_returns_owner_address(mock_provider: MagicMock) -> None:
    client = TonClient(provider=mock_provider)
    addr = await client.resolve_domain("foundation.ton")

    assert addr == "0:9da971000000000000000000000000000000000000000000000000000000001"
    mock_provider.fetch_dns_resolve.assert_called_once_with("foundation.ton")


@pytest.mark.asyncio
async def test_resolve_domain_missing_item() -> None:
    provider = MagicMock()
    provider.fetch_dns_resolve = AsyncMock(return_value={"name": "foundation.ton"})
    provider.aclose = AsyncMock()
    client = TonClient(provider=provider)

    with pytest.raises(TonflowDecodeError, match="item"):
        await client.resolve_domain("foundation.ton")


@pytest.mark.asyncio
async def test_resolve_domain_missing_owner() -> None:
    provider = MagicMock()
    provider.fetch_dns_resolve = AsyncMock(
        return_value={"name": "foundation.ton", "item": {"address": "0:abc"}}
    )
    provider.aclose = AsyncMock()
    client = TonClient(provider=provider)

    with pytest.raises(TonflowDecodeError, match="owner"):
        await client.resolve_domain("foundation.ton")


@pytest.mark.asyncio
async def test_resolve_domain_missing_owner_address() -> None:
    provider = MagicMock()
    provider.fetch_dns_resolve = AsyncMock(
        return_value={"name": "x.ton", "item": {"address": "0:abc", "owner": {}}}
    )
    provider.aclose = AsyncMock()
    client = TonClient(provider=provider)

    with pytest.raises(TonflowDecodeError, match="address"):
        await client.resolve_domain("x.ton")
