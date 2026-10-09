"""Client entry points for reading TON blockchain data."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

import httpx

from tonflow.addresses import normalize_address
from tonflow.cache import AsyncJSONCache, JSONCache
from tonflow.exceptions import TonflowDecodeError
from tonflow.jettons import decode_jetton_transfer
from tonflow.models import (
    Balance,
    JettonTransfer,
    Message,
    MessageDirection,
    NftAttribute,
    NftMetadata,
    RawPayload,
    Transaction,
    TransactionStatus,
)
from tonflow.providers import Provider, TonAPIProvider


@dataclass(slots=True)
class TonClient:
    """High-level async TON API client.

    By default uses :class:`~tonflow.providers.TonAPIProvider`. Pass a custom
    ``provider`` to switch to TonCenter or any other backend without changing
    the rest of your code::

        client = TonClient(provider=TonCenterProvider(api_key="..."))

    For backward compatibility, ``endpoint`` and ``api_key`` are still accepted
    and implicitly create a :class:`~tonflow.providers.TonAPIProvider`.
    """

    endpoint: str = ""
    api_key: str | None = None
    timeout: float = 10.0
    http_client: httpx.AsyncClient | None = None
    cache: JSONCache | AsyncJSONCache | None = None
    cache_ttl_seconds: float | None = 30.0
    provider: Provider | None = None
    _provider: Provider = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.provider is not None:
            self._provider = self.provider
        else:
            self._provider = TonAPIProvider(
                endpoint=self.endpoint,
                api_key=self.api_key,
                timeout=self.timeout,
                http_client=self.http_client,
            )

    async def __aenter__(self) -> TonClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying provider's HTTP client."""
        await self._provider.aclose()

    async def get_transactions(
        self,
        address: str,
        *,
        limit: int = 20,
        before_lt: int | None = None,
    ) -> list[Transaction]:
        """Fetch and normalize account transactions."""
        normalized = normalize_address(address)
        if limit <= 0:
            msg = "limit must be greater than zero."
            raise ValueError(msg)
        if before_lt is not None and before_lt < 0:
            msg = "before_lt must be greater than or equal to zero."
            raise ValueError(msg)

        cache_key = f"txs:{normalized}:{limit}:{before_lt}"
        if self.cache is not None:
            cached = await _cache_get(self.cache, cache_key)
            if isinstance(cached, dict):
                items = cached.get("items")
                if isinstance(items, list):
                    return [Transaction.model_validate(item) for item in items]

        raw_list = await self._provider.fetch_raw_transactions(
            normalized, limit=limit, before_lt=before_lt
        )
        transactions = [_parse_transaction(item, account=normalized) for item in raw_list]

        if self.cache is not None:
            await _cache_set(
                self.cache,
                cache_key,
                {"items": [t.model_dump(mode="json") for t in transactions]},
                self.cache_ttl_seconds,
            )

        return transactions

    async def get_balance(self, address: str) -> Balance:
        """Return the account balance as a :class:`~tonflow.models.Balance`.

        ``Balance.nano`` contains the raw nanoton value (integer, no precision
        loss). ``Balance.ton`` contains the human-readable TON amount as a
        :class:`~decimal.Decimal`.

        Example::

            b = await client.get_balance("EQ...")
            print(f"{b.ton:.2f} TON  ({b.nano} nanotons)")
        """
        from decimal import Decimal

        normalized = normalize_address(address)
        nano = await self._provider.fetch_balance(normalized)
        return Balance(nano=nano, ton=Decimal(nano) / Decimal(10**9))

    async def get_nft_metadata(self, address: str) -> NftMetadata:
        """Return metadata for the NFT at *address*.

        Fetches ``GET /v2/nfts/{address}`` from TonAPI and returns a typed
        :class:`~tonflow.models.NftMetadata` model.

        Example::

            nft = await client.get_nft_metadata("0:78dfe5...")
            print(nft.name, nft.collection_name)
        """
        normalized = normalize_address(address)
        payload = await self._provider.fetch_nft_metadata(normalized)
        return _parse_nft_metadata(payload)

    async def resolve_domain(self, domain: str) -> str:
        """Resolve a TON DNS domain to its owner wallet address.

        Fetches ``GET /v2/dns/{domain}`` from TonAPI and returns the raw address
        string of the wallet that owns the domain.

        Example::

            addr = await client.resolve_domain("foundation.ton")
            print(addr)  # 0:9da971...
        """
        payload = await self._provider.fetch_dns_resolve(domain)
        return _parse_dns_owner(payload)

    async def get_jetton_transfers(
        self,
        address: str,
        *,
        limit: int = 20,
        before_lt: int | None = None,
        decimals: int = 9,
        jetton_minter: str | None = None,
        symbol: str | None = None,
    ) -> list[JettonTransfer]:
        """Fetch transactions for *address* and return only Jetton transfer events.

        Internally calls :meth:`get_transactions` and filters messages whose
        op_code matches a TEP-74 Jetton transfer or transfer_notification.

        Args:
            address: TON account address to query.
            limit: Maximum number of transactions to scan (not transfers).
            before_lt: Return transactions with logical time below this value.
            decimals: Token decimal places used for amount normalization.
            jetton_minter: Optional minter contract address to attach to results.
            symbol: Optional token symbol to attach to results.

        Returns:
            List of :class:`~tonflow.models.JettonTransfer` in the order they
            appear across the fetched transactions (newest transaction first,
            matching the API order).
        """
        transactions = await self.get_transactions(address, limit=limit, before_lt=before_lt)

        transfers: list[JettonTransfer] = []
        for tx in transactions:
            messages: list[Message] = []
            if tx.in_message is not None:
                messages.append(tx.in_message)
            messages.extend(tx.out_messages)

            for msg in messages:
                result = decode_jetton_transfer(
                    tx,
                    msg,
                    decimals=decimals,
                    jetton_minter=jetton_minter,
                    symbol=symbol,
                )
                if result is not None:
                    transfers.append(result)

        return transfers


# ---------------------------------------------------------------------------
# Transaction parsing helpers
# ---------------------------------------------------------------------------


def _parse_transaction(raw: RawPayload, *, account: str) -> Transaction:
    transaction_hash = _required_str(raw, "hash")
    logical_time = _required_int(raw, "lt", fallback_keys=("logical_time",))

    return Transaction(
        hash=transaction_hash,
        account=account,
        lt=logical_time,
        timestamp=_optional_int(raw, "now", fallback_keys=("timestamp", "utime")),
        status=_parse_status(raw),
        in_message=_parse_message(
            raw.get("in_msg") or raw.get("in_message"), MessageDirection.INBOUND
        ),
        out_messages=tuple(
            _parse_required_message(item, MessageDirection.OUTBOUND)
            for item in _raw_message_list(raw.get("out_msgs") or raw.get("out_messages"))
        ),
        total_fees=_optional_int(raw, "total_fees", fallback_keys=("fee",)),
        raw=raw,
    )


def _parse_message(raw: object, direction: MessageDirection) -> Message | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise TonflowDecodeError("TON API message must be an object.")

    return Message(
        source=_optional_str(raw, "source", fallback_keys=("src",)),
        destination=_optional_str(raw, "destination", fallback_keys=("dst",)),
        direction=direction,
        value=_optional_int(raw, "value", fallback_keys=("amount",)),
        body=_optional_body(raw),
        op_code=_optional_int(raw, "op_code", fallback_keys=("opcode",)),
        raw=raw,
    )


def _parse_required_message(raw: object, direction: MessageDirection) -> Message:
    message = _parse_message(raw, direction)
    if message is None:
        raise TonflowDecodeError("TON API message cannot be null in this field.")
    return message


def _raw_message_list(raw: object) -> list[object]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TonflowDecodeError("TON API out messages field must be a list.")
    return raw


def _parse_status(raw: RawPayload) -> TransactionStatus:
    if raw.get("success") is True:
        return TransactionStatus.SUCCESS
    if raw.get("success") is False:
        return TransactionStatus.FAILED

    status = _optional_str(raw, "status")
    if status in {TransactionStatus.SUCCESS, "ok"}:
        return TransactionStatus.SUCCESS
    if status in {TransactionStatus.FAILED, "error"}:
        return TransactionStatus.FAILED
    return TransactionStatus.UNKNOWN


def _optional_body(raw: RawPayload) -> str | None:
    body = _optional_str(raw, "body")
    if body is not None:
        return body

    decoded_body = raw.get("decoded_body")
    if isinstance(decoded_body, dict):
        text = decoded_body.get("text") or decoded_body.get("comment")
        if isinstance(text, str):
            return text
    return None


def _required_str(raw: RawPayload, key: str, *, fallback_keys: tuple[str, ...] = ()) -> str:
    value = _optional_str(raw, key, fallback_keys=fallback_keys)
    if value is None:
        raise TonflowDecodeError(f"TON API transaction is missing required field '{key}'.")
    return value


def _optional_str(raw: RawPayload, key: str, *, fallback_keys: tuple[str, ...] = ()) -> str | None:
    value = _first_value(raw, key, fallback_keys)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TonflowDecodeError(f"TON API field '{key}' must be a string.")
    return value


def _required_int(raw: RawPayload, key: str, *, fallback_keys: tuple[str, ...] = ()) -> int:
    value = _optional_int(raw, key, fallback_keys=fallback_keys)
    if value is None:
        raise TonflowDecodeError(f"TON API transaction is missing required field '{key}'.")
    return value


def _optional_int(raw: RawPayload, key: str, *, fallback_keys: tuple[str, ...] = ()) -> int | None:
    value = _first_value(raw, key, fallback_keys)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise TonflowDecodeError(f"TON API field '{key}' must be an integer.")


def _first_value(raw: RawPayload, key: str, fallback_keys: tuple[str, ...]) -> object:
    if key in raw:
        return raw[key]
    for fallback_key in fallback_keys:
        if fallback_key in raw:
            return raw[fallback_key]
    return None


# ---------------------------------------------------------------------------
# NFT / DNS parsing helpers
# ---------------------------------------------------------------------------


def _parse_nft_metadata(payload: RawPayload) -> NftMetadata:
    address = _required_str(payload, "address")

    metadata = payload.get("metadata")
    name: str | None = None
    description: str | None = None
    image: str | None = None
    attributes: list[NftAttribute] = []
    if isinstance(metadata, dict):
        name = _optional_str(metadata, "name")
        description = _optional_str(metadata, "description")
        image = _optional_str(metadata, "image")
        raw_attrs = metadata.get("attributes")
        if isinstance(raw_attrs, list):
            for item in raw_attrs:
                if isinstance(item, dict):
                    trait = item.get("trait_type")
                    val = item.get("value")
                    if isinstance(trait, str) and val is not None:
                        attributes.append(NftAttribute(trait_type=trait, value=str(val)))

    collection_address: str | None = None
    collection_name: str | None = None
    collection = payload.get("collection")
    if isinstance(collection, dict):
        collection_address = _optional_str(collection, "address")
        collection_name = _optional_str(collection, "name")

    owner: str | None = None
    owner_obj = payload.get("owner")
    if isinstance(owner_obj, dict):
        owner = _optional_str(owner_obj, "address")

    dns = _optional_str(payload, "dns")

    return NftMetadata(
        address=address,
        name=name,
        description=description,
        image=image,
        attributes=attributes,
        collection_address=collection_address,
        collection_name=collection_name,
        owner=owner,
        dns=dns,
    )


def _parse_dns_owner(payload: RawPayload) -> str:
    item = payload.get("item")
    if not isinstance(item, dict):
        raise TonflowDecodeError("TON DNS response missing 'item' object.")
    owner = item.get("owner")
    if not isinstance(owner, dict):
        raise TonflowDecodeError("TON DNS response missing 'item.owner' object.")
    address = _optional_str(owner, "address")
    if address is None:
        raise TonflowDecodeError("TON DNS response missing 'item.owner.address'.")
    return address


# ---------------------------------------------------------------------------
# Cache helpers — transparently handle sync (RedisCache, SQLiteCache) and
# async (AsyncRedisCache) backends.
# ---------------------------------------------------------------------------


async def _cache_get(cache: Any, key: str) -> object:
    result = cache.get(key)
    if inspect.isawaitable(result):
        return await result
    return result


async def _cache_set(cache: Any, key: str, value: RawPayload, ttl: float | None) -> None:
    result = cache.set(key, value, ttl)
    if inspect.isawaitable(result):
        await result
