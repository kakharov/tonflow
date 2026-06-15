"""Client entry points for reading TON blockchain data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from tonflow.addresses import normalize_address
from tonflow.cache import JSONCache
from tonflow.exceptions import TonflowAPIError, TonflowDecodeError
from tonflow.models import Message, MessageDirection, RawPayload, Transaction, TransactionStatus


@dataclass(slots=True)
class TonClient:
    """High-level async TON API client."""

    endpoint: str
    api_key: str | None = None
    timeout: float = 10.0
    http_client: httpx.AsyncClient | None = None
    cache: JSONCache | None = None
    cache_ttl_seconds: float | None = 30.0
    _owns_http_client: bool = field(default=False, init=False, repr=False)

    async def __aenter__(self) -> TonClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the owned HTTP client, if tonflow created one."""

        if self.http_client is not None and self._owns_http_client:
            await self.http_client.aclose()
            self.http_client = None
            self._owns_http_client = False

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

        payload = await self._request_json(
            "GET",
            f"/v2/blockchain/accounts/{normalized}/transactions",
            params={"limit": limit, "before_lt": before_lt},
        )
        transactions = _extract_transactions(payload)
        return [_parse_transaction(item, account=normalized) for item in transactions]

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, int | None] | None = None,
    ) -> RawPayload:
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        cache_key = _cache_key(method, path, clean_params)
        if self.cache is not None and method.upper() == "GET":
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        client = self._get_http_client()

        try:
            response = await client.request(method, path, params=clean_params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TonflowAPIError(
                f"TON API request failed with status {exc.response.status_code}.",
                status_code=exc.response.status_code,
                url=str(exc.request.url),
            ) from exc
        except httpx.HTTPError as exc:
            raise TonflowAPIError(f"TON API request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TonflowDecodeError("TON API response is not valid JSON.") from exc

        if not isinstance(data, dict):
            raise TonflowDecodeError("TON API response must be a JSON object.")

        if self.cache is not None and method.upper() == "GET":
            self.cache.set(cache_key, data, ttl_seconds=self.cache_ttl_seconds)
        return data

    def _get_http_client(self) -> httpx.AsyncClient:
        if self.http_client is not None:
            return self.http_client

        headers = {"Accept": "application/json"}
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.http_client = httpx.AsyncClient(
            base_url=self.endpoint.rstrip("/"),
            headers=headers,
            timeout=self.timeout,
        )
        self._owns_http_client = True
        return self.http_client


def _cache_key(method: str, path: str, params: dict[str, int]) -> str:
    query = urlencode(sorted(params.items()))
    if query:
        return f"{method.upper()} {path}?{query}"
    return f"{method.upper()} {path}"


def _extract_transactions(payload: RawPayload) -> list[RawPayload]:
    raw_transactions: Any = payload.get("transactions", payload.get("items"))
    if raw_transactions is None:
        raw_transactions = payload.get("result", [])
    if not isinstance(raw_transactions, list):
        raise TonflowDecodeError("TON API transactions field must be a list.")

    transactions: list[RawPayload] = []
    for item in raw_transactions:
        if not isinstance(item, dict):
            raise TonflowDecodeError("TON API transaction item must be an object.")
        transactions.append(item)
    return transactions


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
