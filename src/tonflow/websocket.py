"""WebSocket-based real-time transaction streaming."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from tonflow.addresses import normalize_address
from tonflow.client import TonClient
from tonflow.models import Transaction


async def stream_transactions_ws(
    client: TonClient,
    address: str,
    *,
    ws_url: str = "wss://tonapi.io/v2/websocket",
    api_key: str | None = None,
) -> AsyncIterator[Transaction]:
    """Stream new transactions in real time via WebSocket (TonAPI).

    Unlike :func:`~tonflow.stream.watch_address` which polls on a fixed
    interval, this opens a persistent connection and receives push
    notifications the moment a transaction lands on-chain.

    When a notification arrives the full transaction is fetched via REST
    so the yielded :class:`~tonflow.models.Transaction` objects are
    identical to those from
    :meth:`~tonflow.client.TonClient.get_transactions`.

    Requires the ``ws`` extra::

        pip install tonflow[ws]

    Args:
        client: A configured :class:`TonClient` instance (used for REST fetches).
        address: TON account address to watch.
        ws_url: TonAPI WebSocket endpoint URL.
        api_key: TonAPI API key. If omitted the connection is unauthenticated
            (subject to stricter rate limits).

    Yields:
        :class:`~tonflow.models.Transaction` objects in the order they arrive.

    Example::

        from tonflow import TonClient
        from tonflow.websocket import stream_transactions_ws

        async with TonClient(endpoint="https://tonapi.io", api_key="...") as client:
            async for tx in stream_transactions_ws(client, "EQ...", api_key="..."):
                print(tx.hash, tx.logical_time)
    """
    try:
        import websockets
    except ImportError:
        raise ImportError(
            "WebSocket streaming requires the 'ws' extra: pip install tonflow[ws]"
        ) from None

    normalized = normalize_address(address)
    url = f"{ws_url}?token={api_key}" if api_key else ws_url

    async with websockets.connect(url) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "subscribe_account",
                    "params": {"accounts": [normalized]},
                }
            )
        )

        async for raw in ws:
            msg = json.loads(raw)

            # Skip subscription confirmation {"id": 1, "result": "success"}
            if "id" in msg and "result" in msg:
                continue

            if msg.get("method") != "account_transaction":
                continue

            result = msg.get("result", {})
            raw_lt = result.get("lt")
            if raw_lt is None:
                continue

            lt = int(raw_lt)

            # Fetch the full transaction — TonAPI returns txs with LT < before_lt,
            # so before_lt = lt + 1 returns the transaction at exactly this LT.
            txs = await client.get_transactions(normalized, limit=1, before_lt=lt + 1)
            for tx in txs:
                if tx.logical_time == lt:
                    yield tx
                    break
