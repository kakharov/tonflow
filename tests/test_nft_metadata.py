"""Tests for TonClient.get_nft_metadata."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tonflow.client import TonClient
from tonflow.exceptions import TonflowDecodeError
from tonflow.models import NftAttribute, NftMetadata

_NFT_PAYLOAD = {
    "address": "0:78dfe54299fd7b3bb60c779d5f02f3a370c902c38e8dff724c0a87a01ff643a3",
    "index": 6207527114634427043,
    "owner": {"address": "0:9da971000000000000000000000000000000000000000000000000000000001"},
    "collection": {
        "address": "0:b774000000000000000000000000000000000000000000000000000000000001",
        "name": "TON DNS Domains",
        "description": "*.ton domains",
    },
    "verified": True,
    "metadata": {
        "name": "foundation.ton",
        "description": "A .ton domain",
        "image": "https://nft.fragment.com/foundation.ton.webp",
        "attributes": [
            {"trait_type": "Length", "value": "10"},
            {"trait_type": "Category", "value": "Common"},
        ],
    },
    "dns": "foundation.ton",
    "trust": "whitelist",
}


@pytest.fixture()
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.fetch_nft_metadata = AsyncMock(return_value=_NFT_PAYLOAD)
    provider.aclose = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_get_nft_metadata_returns_model(mock_provider: MagicMock) -> None:
    client = TonClient(provider=mock_provider)
    nft = await client.get_nft_metadata(
        "0:78dfe54299fd7b3bb60c779d5f02f3a370c902c38e8dff724c0a87a01ff643a3"
    )

    assert isinstance(nft, NftMetadata)
    assert nft.address == "0:78dfe54299fd7b3bb60c779d5f02f3a370c902c38e8dff724c0a87a01ff643a3"
    assert nft.name == "foundation.ton"
    assert nft.description == "A .ton domain"
    assert nft.image == "https://nft.fragment.com/foundation.ton.webp"
    assert nft.dns == "foundation.ton"
    assert nft.collection_name == "TON DNS Domains"
    assert nft.collection_address == (
        "0:b774000000000000000000000000000000000000000000000000000000000001"
    )
    assert nft.owner == (
        "0:9da971000000000000000000000000000000000000000000000000000000001"
    )


@pytest.mark.asyncio
async def test_get_nft_metadata_attributes(mock_provider: MagicMock) -> None:
    client = TonClient(provider=mock_provider)
    nft = await client.get_nft_metadata(
        "0:78dfe54299fd7b3bb60c779d5f02f3a370c902c38e8dff724c0a87a01ff643a3"
    )

    assert len(nft.attributes) == 2
    assert nft.attributes[0] == NftAttribute(trait_type="Length", value="10")
    assert nft.attributes[1] == NftAttribute(trait_type="Category", value="Common")


@pytest.mark.asyncio
async def test_get_nft_metadata_minimal() -> None:
    provider = MagicMock()
    provider.fetch_nft_metadata = AsyncMock(
        return_value={"address": "0:aabbcc", "metadata": {}}
    )
    provider.aclose = AsyncMock()
    client = TonClient(provider=provider)
    nft = await client.get_nft_metadata("0:aabbcc")

    assert nft.address == "0:aabbcc"
    assert nft.name is None
    assert nft.attributes == []
    assert nft.collection_address is None
    assert nft.owner is None


@pytest.mark.asyncio
async def test_get_nft_metadata_missing_address() -> None:
    provider = MagicMock()
    provider.fetch_nft_metadata = AsyncMock(return_value={"metadata": {}})
    provider.aclose = AsyncMock()
    client = TonClient(provider=provider)

    with pytest.raises(TonflowDecodeError):
        await client.get_nft_metadata("0:aabbcc")
