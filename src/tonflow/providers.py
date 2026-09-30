"""Pluggable provider adapters for TON API endpoints."""

from __future__ import annotations

import asyncio
import base64
import random
from typing import Any, Protocol, runtime_checkable

import httpx

from tonflow.exceptions import TonflowAPIError, TonflowDecodeError
from tonflow.models import RawPayload

# Status codes that are worth retrying (rate-limit and transient server errors).
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


@runtime_checkable
class Provider(Protocol):
    """Protocol for TON data provider adapters.

    Implement this to add support for any TON API endpoint
    (TonAPI, TonCenter, Lite Server proxy, etc.).
    """

    async def fetch_raw_transactions(
        self,
        address: str,
        *,
        limit: int,
        before_lt: int | None,
    ) -> list[RawPayload]: ...

    async def fetch_balance(self, address: str) -> int: ...

    async def send_boc(self, boc: str) -> None: ...

    async def aclose(self) -> None: ...


class TonAPIProvider:
    """Provider adapter for TonAPI (tonapi.io).

    This is the default provider used by :class:`~tonflow.client.TonClient`
    when no explicit provider is specified.
    """

    def __init__(
        self,
        endpoint: str = "https://tonapi.io",
        api_key: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
        retry_attempts: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._http_client = http_client
        self._owns_client = http_client is None
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            headers: dict[str, str] = {"Accept": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._http_client = httpx.AsyncClient(
                base_url=self._endpoint.rstrip("/"),
                headers=headers,
                timeout=self._timeout,
            )
        return self._http_client

    async def fetch_raw_transactions(
        self,
        address: str,
        *,
        limit: int,
        before_lt: int | None,
    ) -> list[RawPayload]:
        params: dict[str, Any] = {"limit": limit}
        if before_lt is not None:
            params["before_lt"] = before_lt
        path = f"/v2/blockchain/accounts/{address}/transactions"
        payload = await _request_json(
            self._client(),
            "GET",
            path,
            params=params,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )
        return _extract_list(payload, keys=("transactions", "items"))

    async def fetch_balance(self, address: str) -> int:
        payload = await _request_json(
            self._client(),
            "GET",
            f"/v2/accounts/{address}",
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )
        return _extract_balance(payload, key="balance")

    async def send_boc(self, boc: str) -> None:
        await _request_json(
            self._client(),
            "POST",
            "/v2/blockchain/message",
            params={"boc": boc},
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


class TonCenterProvider:
    """Provider adapter for TonCenter (toncenter.com/api/v2).

    TonCenter is a free public TON API. It has different rate limits and
    response format compared to TonAPI. API key is optional but recommended
    to avoid rate limiting.

    Example::

        provider = TonCenterProvider(api_key="your-key")
        client = TonClient(provider=provider)
    """

    def __init__(
        self,
        endpoint: str = "https://toncenter.com/api/v2",
        api_key: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
        retry_attempts: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._http_client = http_client
        self._owns_client = http_client is None
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self._endpoint.rstrip("/"),
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
        return self._http_client

    async def fetch_raw_transactions(
        self,
        address: str,
        *,
        limit: int,
        before_lt: int | None,
    ) -> list[RawPayload]:
        params: dict[str, Any] = {"address": address, "limit": limit, "to_lt": 0}
        if before_lt is not None:
            params["lt"] = before_lt
        if self._api_key:
            params["api_key"] = self._api_key
        payload = await _request_json(
            self._client(),
            "GET",
            "/getTransactions",
            params=params,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )
        raw_list = _extract_list(payload, keys=("result",))
        return [_normalize_toncenter_tx(item) for item in raw_list]

    async def fetch_balance(self, address: str) -> int:
        params: dict[str, Any] = {"address": address}
        if self._api_key:
            params["api_key"] = self._api_key
        payload = await _request_json(
            self._client(),
            "GET",
            "/getAddressBalance",
            params=params,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )
        return _extract_balance(payload, key="result")

    async def send_boc(self, boc: str) -> None:
        params: dict[str, Any] = {"boc": boc}
        if self._api_key:
            params["api_key"] = self._api_key
        await _request_json(
            self._client(),
            "POST",
            "/sendBoc",
            params=params,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


# ---------------------------------------------------------------------------
# Failover provider
# ---------------------------------------------------------------------------


class FailoverProvider:
    """Tries *primary* first; falls back to *fallback* on API errors.

    Useful for high-availability setups where TonAPI is the preferred endpoint
    but TonCenter (or any other provider) is used as a backup::

        from tonflow import TonClient
        from tonflow.providers import FailoverProvider, TonAPIProvider, TonCenterProvider

        primary = TonAPIProvider(api_key="tonapi-key")
        fallback = TonCenterProvider(api_key="toncenter-key")
        client = TonClient(provider=FailoverProvider(primary, fallback))
    """

    def __init__(self, primary: Provider, fallback: Provider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def fetch_raw_transactions(
        self,
        address: str,
        *,
        limit: int,
        before_lt: int | None,
    ) -> list[RawPayload]:
        try:
            return await self._primary.fetch_raw_transactions(
                address, limit=limit, before_lt=before_lt
            )
        except TonflowAPIError:
            return await self._fallback.fetch_raw_transactions(
                address, limit=limit, before_lt=before_lt
            )

    async def fetch_balance(self, address: str) -> int:
        try:
            return await self._primary.fetch_balance(address)
        except TonflowAPIError:
            return await self._fallback.fetch_balance(address)

    async def send_boc(self, boc: str) -> None:
        try:
            await self._primary.send_boc(boc)
        except TonflowAPIError:
            await self._fallback.send_boc(boc)

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._fallback.aclose()


# ---------------------------------------------------------------------------
# TonCenter response normalization
# ---------------------------------------------------------------------------


def _normalize_toncenter_tx(raw: RawPayload) -> RawPayload:
    """Flatten TonCenter transaction_id into top-level hash/lt fields."""
    result: dict[str, Any] = dict(raw)
    tx_id = raw.get("transaction_id")
    if isinstance(tx_id, dict):
        if "hash" not in result:
            result["hash"] = tx_id.get("hash")
        if "lt" not in result:
            result["lt"] = tx_id.get("lt")
    in_msg = result.get("in_msg")
    if isinstance(in_msg, dict):
        result["in_msg"] = _normalize_toncenter_msg(in_msg)
    out_msgs = result.get("out_msgs")
    if isinstance(out_msgs, list):
        result["out_msgs"] = [
            _normalize_toncenter_msg(m) if isinstance(m, dict) else m for m in out_msgs
        ]
    return result


def _normalize_toncenter_msg(msg: RawPayload) -> RawPayload:
    """Decode base64 text from TonCenter msg_data into a body field."""
    result: dict[str, Any] = dict(msg)
    if "body" not in result:
        msg_data = msg.get("msg_data")
        if isinstance(msg_data, dict):
            text = msg_data.get("text")
            if isinstance(text, str):
                try:
                    result["body"] = base64.b64decode(text).decode("utf-8", errors="replace")
                except Exception:
                    result["body"] = text
    return result


# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    retry_attempts: int = 1,
    retry_backoff: float = 0.5,
) -> RawPayload:
    for attempt in range(max(1, retry_attempts)):
        try:
            response = await client.request(method, path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            err = TonflowAPIError(
                f"TON API request failed with status {status}.",
                status_code=status,
                url=str(exc.request.url),
            )
            if status in _RETRYABLE_STATUSES and attempt < retry_attempts - 1:
                delay = retry_backoff * (2**attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
                continue
            raise err from exc
        except httpx.HTTPError as exc:
            raise TonflowAPIError(f"TON API request failed: {exc}") from exc
        break  # success

    try:
        data = response.json()
    except ValueError as exc:
        raise TonflowDecodeError("TON API response is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise TonflowDecodeError("TON API response must be a JSON object.")

    return data


def _extract_balance(payload: RawPayload, *, key: str) -> int:
    value = payload.get(key)
    if value is None:
        raise TonflowDecodeError(f"TON API balance response missing field '{key}'.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TonflowDecodeError(f"TON API balance field '{key}' must be an integer.") from exc


def _extract_list(payload: RawPayload, *, keys: tuple[str, ...]) -> list[RawPayload]:
    value: Any = None
    for key in keys:
        value = payload.get(key)
        if value is not None:
            break

    if value is None:
        value = []

    if not isinstance(value, list):
        raise TonflowDecodeError("TON API transactions field must be a list.")

    result: list[RawPayload] = []
    for item in value:
        if not isinstance(item, dict):
            raise TonflowDecodeError("TON API transaction item must be an object.")
        result.append(item)
    return result
