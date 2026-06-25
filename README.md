# tonflow

[![CI](https://github.com/kakharov/tonflow/actions/workflows/ci.yml/badge.svg)](https://github.com/kakharov/tonflow/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/kakharov/tonflow/branch/main/graph/badge.svg)](https://codecov.io/gh/kakharov/tonflow)
[![PyPI](https://img.shields.io/pypi/v/tonflow)](https://pypi.org/project/tonflow/)
[![Python](https://img.shields.io/pypi/pyversions/tonflow)](https://pypi.org/project/tonflow/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Python toolkit for reading, decoding, normalizing, and locally caching TON blockchain data.

`tonflow` is a lightweight MIT-licensed library. It does not run a hosted indexer and does not store blockchain data on your behalf — any cache lives on your own machine or infrastructure.

> See [CHANGELOG.md](CHANGELOG.md) for a full version history.

## Install

```bash
pip install tonflow
```

Optional extras:

```bash
pip install tonflow[redis]   # Redis cache backend
pip install tonflow[ws]      # WebSocket streaming
pip install tonflow[redis,ws] # both
```

Requires Python 3.12+.

## Quickstart

```python
import asyncio
from tonflow import TonClient

async def main() -> None:
    async with TonClient(endpoint="https://tonapi.io") as client:
        txs = await client.get_transactions("EQ...", limit=10)
        for tx in txs:
            print(tx.hash, tx.logical_time, tx.status)

asyncio.run(main())
```

## Recipes

### Get Jetton transfers

```python
transfers = await client.get_jetton_transfers(
    "EQ...",
    limit=20,
    decimals=6,
    symbol="USDT",
)
for t in transfers:
    print(t.sender, "→", t.recipient, t.amount, t.symbol)
```

### Stream new transactions (polling)

```python
from tonflow import watch_address

async for tx in watch_address(client, "EQ...", interval_seconds=5):
    print("new tx:", tx.hash, tx.logical_time)
```

`watch_address` runs indefinitely. To stop it after a fixed duration:

```python
import asyncio

async with asyncio.timeout(60):
    async for tx in watch_address(client, "EQ..."):
        print(tx.hash)
```

### Stream new transactions (WebSocket)

Lower latency alternative — push notifications instead of polling.
Requires `pip install tonflow[ws]`.

```python
from tonflow.websocket import stream_transactions_ws

async for tx in stream_transactions_ws(client, "EQ...", api_key="..."):
    print(tx.hash, tx.logical_time)
```

### Send a transaction and wait for confirmation

```python
from time import time
from tonflow import send_and_confirm

# boc is a base64-encoded signed external message — build it with
# a wallet library such as pytoniq or tonsdk
tx = await send_and_confirm(
    client,
    wallet_address,
    boc,
    timeout=60,
    valid_until=int(time()) + 60,
)
print("confirmed:", tx.hash, tx.logical_time)
```

### Use a different API provider

```python
from tonflow import TonClient, TonCenterProvider

# TonCenter is free; api_key is optional but recommended
client = TonClient(provider=TonCenterProvider(api_key="your-key"))
```

### Cache responses locally

```python
from tonflow import TonClient, SQLiteCache

client = TonClient(
    endpoint="https://tonapi.io",
    cache=SQLiteCache(".tonflow/cache.sqlite3"),
    cache_ttl_seconds=60,
)
```

### Cache with Redis (production)

Requires `pip install tonflow[redis]`.

```python
import redis
from tonflow import TonClient, RedisCache

cache = RedisCache(redis.Redis(host="localhost"), prefix="myapp:")
client = TonClient(endpoint="https://tonapi.io", cache=cache, cache_ttl_seconds=30)
```

### Decode Jetton burn and mint events

```python
from tonflow import extract_jetton_burns, extract_jetton_mints

burns = extract_jetton_burns(tx, decimals=9, symbol="JETTON")
mints = extract_jetton_mints(tx, decimals=9, symbol="JETTON")
```

### Export to CSV or JSON

```python
from tonflow import jetton_transfers_to_csv, transactions_to_json

json_str = transactions_to_json(txs, indent=2)
csv_str  = jetton_transfers_to_csv(transfers)

with open("transfers.csv", "w") as f:
    f.write(csv_str)
```

### Validate a TON address

```python
from tonflow import validate_address, is_user_friendly_address, is_raw_address

validate_address("EQ...")           # raises ValueError if invalid
is_user_friendly_address("EQ...")   # True / False
is_raw_address("0:abcd...")         # True / False
```

## API reference

### `TonClient`

```python
TonClient(
    endpoint: str = "",
    api_key: str | None = None,
    timeout: float = 10.0,
    cache: JSONCache | None = None,
    cache_ttl_seconds: float | None = 30.0,
    provider: Provider | None = None,
)
```

| Method | Description |
|---|---|
| `get_transactions(address, limit, before_lt)` | Fetch and normalize account transactions |
| `get_jetton_transfers(address, limit, before_lt, decimals, jetton_minter, symbol)` | Fetch transactions and return only Jetton transfer events |
| `aclose()` | Close the underlying HTTP client |

Use as an async context manager (`async with`) for automatic cleanup.

### Providers

| Class | Description |
|---|---|
| `TonAPIProvider(endpoint, api_key, timeout)` | Default. Uses Bearer token auth. |
| `TonCenterProvider(endpoint, api_key, timeout)` | Free public API. `api_key` optional but recommended. |

Pass any provider to `TonClient(provider=...)`. Implement the `Provider` protocol to add your own.

### `send_and_confirm`

```python
send_and_confirm(
    client: TonClient,
    address: str,
    boc: str,
    timeout: float = 60.0,
    poll_interval: float = 3.0,
    valid_until: int | None = None,
) -> Transaction
```

Broadcasts a signed BOC and polls until the transaction appears on-chain.
`valid_until` is a Unix timestamp — if it passes before confirmation,
`TonflowExpiredError` is raised immediately (the message is permanently rejected;
build a new one with an updated `seqno`).

### `watch_address`

```python
watch_address(
    client: TonClient,
    address: str,
    interval_seconds: float = 5.0,
    lookback: int = 10,
) -> AsyncIterator[Transaction]
```

Polls every `interval_seconds`. Seeds a baseline on the first call so existing transactions are not replayed. Yields new transactions in ascending logical-time order.

### `stream_transactions_ws`

```python
stream_transactions_ws(
    client: TonClient,
    address: str,
    ws_url: str = "wss://tonapi.io/v2/websocket",
    api_key: str | None = None,
) -> AsyncIterator[Transaction]
```

Push-based streaming via TonAPI WebSocket. Requires `pip install tonflow[ws]`.
Note: does not reconnect automatically on connection drop.

### Models

| Model | Key fields |
|---|---|
| `Transaction` | `hash`, `account`, `logical_time`, `timestamp`, `status`, `in_message`, `out_messages`, `total_fees` |
| `Message` | `source`, `destination`, `direction`, `value`, `body`, `op_code` |
| `JettonTransfer` | `transaction_hash`, `sender`, `recipient`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter`, `comment` |
| `JettonBurn` | `transaction_hash`, `sender`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter` |
| `JettonMint` | `transaction_hash`, `recipient`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter` |

### Cache backends

| Class | Storage | Best for |
|---|---|---|
| `InMemoryCache` | In-process dict | Tests, short-lived scripts |
| `SQLiteCache(path)` | SQLite file on disk | Local scripts, small services |
| `RedisCache(client, prefix)` | Redis | Production services (`pip install tonflow[redis]`) |

All implement the `JSONCache` protocol — you can write your own backend by implementing `get`, `set`, and `clear`.

> **Note:** `RedisCache` uses a synchronous Redis client. In a fully async service, calls to Redis will briefly block the event loop. For long-running high-throughput services consider wrapping calls in `asyncio.get_event_loop().run_in_executor()`.

### Export helpers

| Function | Output |
|---|---|
| `transactions_to_json(txs, indent=None)` | JSON string |
| `transactions_to_csv(txs)` | CSV string |
| `jetton_transfers_to_json(transfers, indent=None)` | JSON string |
| `jetton_transfers_to_csv(transfers)` | CSV string |

`Decimal` amounts are serialized as strings to preserve precision.

### Address helpers

| Function | Description |
|---|---|
| `normalize_address(addr)` | Strip whitespace, raise on empty |
| `is_user_friendly_address(addr)` | Validate EQ/UQ/kQ/0Q 48-char format |
| `is_raw_address(addr)` | Validate `workchain:64hexchars` format |
| `validate_address(addr)` | Accept either format, raise `ValueError` on invalid |

### Exceptions

| Exception | Raised when |
|---|---|
| `TonflowAPIError` | HTTP error from upstream TON API |
| `TonflowDecodeError` | API response cannot be parsed into expected models |
| `TonflowTimeoutError` | `send_and_confirm` timeout elapsed without confirmation |
| `TonflowExpiredError` | `valid_until` passed before the transaction was confirmed |

## Examples

See the [`examples/`](examples/) directory:

**0.1.0**
- [`get_transactions.py`](examples/get_transactions.py) — fetch and print recent transactions
- [`get_jetton_transfers.py`](examples/get_jetton_transfers.py) — fetch and print Jetton transfers
- [`watch_address.py`](examples/watch_address.py) — polling stream for new transactions
- [`export_to_csv.py`](examples/export_to_csv.py) — save transactions and transfers to CSV
- [`cache_with_sqlite.py`](examples/cache_with_sqlite.py) — local SQLite cache in action

**0.2.0**
- [`toncenter_provider.py`](examples/toncenter_provider.py) — switch to TonCenter API
- [`stream_websocket.py`](examples/stream_websocket.py) — real-time WebSocket streaming
- [`send_and_confirm.py`](examples/send_and_confirm.py) — broadcast BOC and wait for confirmation
- [`cache_with_redis.py`](examples/cache_with_redis.py) — Redis cache backend
- [`jetton_burn_mint.py`](examples/jetton_burn_mint.py) — decode Jetton burn and mint events

## Development

```powershell
git clone https://github.com/kakharov/tonflow
cd tonflow
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Lint and type check:

```bash
ruff check .
ruff format .
mypy src/
```

## Roadmap

### `0.2.0` — current
- [x] Pluggable provider system (`TonAPIProvider`, `TonCenterProvider`)
- [x] `send_and_confirm()` — broadcast BOC and poll until on-chain confirmation
- [x] WebSocket streaming via TonAPI (`stream_transactions_ws`)
- [x] Jetton burn and mint event decoding (TEP-74)
- [x] Redis cache adapter

### `0.1.0`
- [x] `TonClient` with `get_transactions()` and `get_jetton_transfers()`
- [x] TEP-74 Jetton transfer decoder
- [x] `SQLiteCache` and `InMemoryCache` with TTL
- [x] `watch_address()` polling stream
- [x] Address validation (user-friendly and raw formats)
- [x] JSON and CSV export helpers

### `0.3.0` — planned
- [ ] NFT transfer event decoding
- [ ] CLI: `tonflow scan <address>`
- [ ] Postgres export helper
- [ ] Backfill utility for historical data

## License

MIT
