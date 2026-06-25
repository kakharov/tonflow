"""Pluggable provider adapters for TON API endpoints."""

from __future__ import annotations

import base64
from typing import Any, Protocol, runtime_checkable

import httpx

from tonflow.exceptions import TonflowAPIError, TonflowDecodeError
from tonflow.models import RawPayload


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

    async def send_boc(self, boc: str) -> None: ...

    async def aclose(self) -> None: ...


class TonAPIProvider:
    """Provider adapter for TonAPI (tonapi.io).

    This is the default provider used by :class:`~tonflow.client.TonClient`
    when no explicit provider is specified.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._http_client = http_client
        self._owns_client = http_client is None

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
        payload = await _request_json(self._client(), "GET", path, params=params)
        return _extract_list(payload, keys=("transactions", "items"))

    async def send_boc(self, boc: str) -> None:
        """Broadcast a signed external message (BOC) to the network."""
        await _request_json(
            self._client(), "POST", "/v2/blockchain/message", params={"boc": boc}
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
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._http_client = http_client
        self._owns_client = http_client is None

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
        payload = await _request_json(self._client(), "GET", "/getTransactions", params=params)
        raw_list = _extract_list(payload, keys=("result",))
        return [_normalize_toncenter_tx(item) for item in raw_list]

    async def send_boc(self, boc: str) -> None:
        """Broadcast a signed external message (BOC) to the network."""
        params: dict[str, Any] = {"boc": boc}
        if self._api_key:
            params["api_key"] = self._api_key
        await _request_json(self._client(), "POST", "/sendBoc", params=params)

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


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
) -> RawPayload:
    try:
        response = await client.request(method, path, params=params)
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

    return data


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
