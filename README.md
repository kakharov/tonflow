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

### Watch multiple addresses

```python
from tonflow import watch_addresses

async for tx in watch_addresses(client, ["EQ...", "UQ...", "EQ2..."]):
    print(tx.account, tx.hash)
```

### Stream new transactions (WebSocket)

Lower latency alternative — push notifications instead of polling.
Requires `pip install tonflow[ws]`. Reconnects automatically on network drops.

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

### Automatic failover between providers

```python
from tonflow import TonClient
from tonflow.providers import FailoverProvider, TonAPIProvider, TonCenterProvider

provider = FailoverProvider(
    TonAPIProvider(api_key="tonapi-key"),
    TonCenterProvider(api_key="toncenter-key"),
)
client = TonClient(provider=provider)
```

### Tune retry behaviour

```python
from tonflow.providers import TonAPIProvider
from tonflow import TonClient

# Up to 5 attempts, starting at 1 s backoff; doubles each attempt
provider = TonAPIProvider(api_key="...", retry_attempts=5, retry_backoff=1.0)
client = TonClient(provider=provider)
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

Sync client (simple, small services):

```python
import redis
from tonflow import TonClient, RedisCache

cache = RedisCache(redis.Redis(host="localhost"), prefix="myapp:")
client = TonClient(endpoint="https://tonapi.io", cache=cache, cache_ttl_seconds=30)
```

Async client (recommended for long-running async services):

```python
import redis.asyncio as aioredis
from tonflow import TonClient, AsyncRedisCache

r = aioredis.Redis(host="localhost", port=6379, db=0)
cache = AsyncRedisCache(r, prefix="myapp:")
client = TonClient(endpoint="https://tonapi.io", cache=cache, cache_ttl_seconds=30)
```

### Decode Jetton burn and mint events

```python
from tonflow import extract_jetton_burns, extract_jetton_mints

burns = extract_jetton_burns(tx, decimals=9, symbol="JETTON")
mints = extract_jetton_mints(tx, decimals=9, symbol="JETTON")
```

### Get account balance

```python
b = await client.get_balance("EQ...")
print(f"{b.ton:.9f} TON  ({b.nano} nanotons)")
```

### Backfill all historical transactions

```python
from tonflow import backfill_transactions

async for tx in backfill_transactions(client, "EQ...", page_size=100):
    print(tx.hash, tx.logical_time)
```

Stop at a known logical time to avoid re-processing old data:

```python
async for tx in backfill_transactions(client, "EQ...", stop_before_lt=42000000):
    process(tx)
```

### Export to SQL (Postgres)

```python
from tonflow import transactions_to_sql, jetton_transfers_to_sql

sql = transactions_to_sql(txs)
# sql includes CREATE TABLE IF NOT EXISTS + INSERT ... ON CONFLICT (hash) DO NOTHING
with open("dump.sql", "w") as f:
    f.write(sql)
```

### Export to CSV or JSON

```python
from tonflow import jetton_transfers_to_csv, transactions_to_json

json_str = transactions_to_json(txs, indent=2)
csv_str = jetton_transfers_to_csv(transfers)

with open("transfers.csv", "w") as f:
    f.write(csv_str)
```

### Validate a TON address

```python
from tonflow import validate_address, is_user_friendly_address, is_raw_address

validate_address("EQ...")  # raises ValueError if invalid
is_user_friendly_address("EQ...")  # True / False
is_raw_address("0:abcd...")  # True / False
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
| `get_balance(address)` | Return `Balance(nano, ton)` for the account |
| `aclose()` | Close the underlying HTTP client |

Use as an async context manager (`async with`) for automatic cleanup.

### Providers

| Class | Description |
|---|---|
| `TonAPIProvider(endpoint, api_key, timeout, retry_attempts, retry_backoff)` | Default. Uses Bearer token auth. |
| `TonCenterProvider(endpoint, api_key, timeout, retry_attempts, retry_backoff)` | Free public API. `api_key` optional but recommended. |
| `FailoverProvider(primary, fallback)` | Tries primary; switches to fallback on any `TonflowAPIError`. |

Both concrete providers retry retryable HTTP errors (`429`, `5xx`) automatically.
Default: `retry_attempts=3`, `retry_backoff=0.5` (seconds, doubles each attempt with jitter).

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

### `get_balance`

```python
await client.get_balance(address: str) -> Balance
```

Returns `Balance(nano: int, ton: Decimal)`. `nano` is the raw nanoton value (no precision loss);
`ton` is `Decimal(nano) / Decimal(10**9)`. Delegates to the configured provider without caching.

### `backfill_transactions`

```python
backfill_transactions(
    client: TonClient,
    address: str,
    *,
    page_size: int = 100,
    stop_before_lt: int | None = None,
) -> AsyncIterator[Transaction]
```

Async generator that pages through all historical transactions newest-first. Bypasses the cache so results always reflect the current chain state. Stops when there are no more pages or when `stop_before_lt` is reached (exclusive).

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

### `watch_addresses`

```python
watch_addresses(
    client: TonClient,
    addresses: list[str],
    interval_seconds: float = 5.0,
    lookback: int = 10,
) -> AsyncIterator[Transaction]
```

Runs one `watch_address` per address in parallel and merges all events into a single stream.
Events arrive in order of delivery (not global logical time).

### `stream_transactions_ws`

```python
stream_transactions_ws(
    client: TonClient,
    address: str,
    ws_url: str = "wss://tonapi.io/v2/websocket",
    api_key: str | None = None,
    reconnect: bool = True,
) -> AsyncIterator[Transaction]
```

Push-based streaming via TonAPI WebSocket. Requires `pip install tonflow[ws]`.
With `reconnect=True` (default) reconnects automatically on connection drop with
exponential backoff (1 s → 2 s → 4 s … up to 60 s).

### Models

| Model | Key fields |
|---|---|
| `Transaction` | `hash`, `account`, `logical_time`, `timestamp`, `status`, `in_message`, `out_messages`, `total_fees` |
| `Message` | `source`, `destination`, `direction`, `value`, `body`, `op_code` |
| `Balance` | `nano: int`, `ton: Decimal` |
| `JettonTransfer` | `transaction_hash`, `sender`, `recipient`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter`, `comment` |
| `JettonBurn` | `transaction_hash`, `sender`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter` |
| `JettonMint` | `transaction_hash`, `recipient`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter` |
| `NftTransfer` | `transaction_hash`, `sender`, `recipient`, `nft_address`, `nft_collection`, `comment` |

### NFT helpers

| Function | Description |
|---|---|
| `extract_nft_transfers(tx, nft_collection=None)` | Return all `NftTransfer` events from a transaction |
| `decode_nft_transfer(tx, msg, nft_collection=None)` | Decode a single message into `NftTransfer` |
| `is_nft_transfer(msg)` | True if message op code is `0x5FCC3D14` |
| `is_nft_ownership_assigned(msg)` | True if message op code is `0x05138D91` |

### CLI

```
tonflow scan <address> [--limit N] [--provider tonapi|toncenter] [--endpoint URL] [--api-key KEY]
tonflow balance <address> [--provider tonapi|toncenter] [--endpoint URL] [--api-key KEY]
```

`tonflow scan` prints a table of recent transactions (hash, logical time, status, fees, timestamp).  
`tonflow balance` prints the balance in TON and nanotons.

When `--provider toncenter` is used without a custom `--endpoint`, the default TonCenter endpoint is used automatically.

### Cache backends

| Class | Storage | Best for |
|---|---|---|
| `InMemoryCache` | In-process dict | Tests, short-lived scripts |
| `SQLiteCache(path)` | SQLite file on disk | Local scripts, small services |
| `RedisCache(client, prefix)` | Redis (sync) | Services where sync Redis is already in use |
| `AsyncRedisCache(client, prefix)` | Redis (async) | Long-running async services (`pip install tonflow[redis]`) |

`TonClient` detects sync vs async backends automatically.
All implement the same `get` / `set` / `clear` interface — you can write your own backend.

### Export helpers

| Function | Output |
|---|---|
| `transactions_to_json(txs, indent=None)` | JSON string |
| `transactions_to_csv(txs)` | CSV string |
| `transactions_to_sql(txs, include_ddl=True)` | Postgres-compatible SQL with `ON CONFLICT (hash) DO NOTHING` |
| `jetton_transfers_to_json(transfers, indent=None)` | JSON string |
| `jetton_transfers_to_csv(transfers)` | CSV string |
| `jetton_transfers_to_sql(transfers, include_ddl=True)` | Postgres-compatible SQL |

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

**0.3.0**
- [`nft_transfers.py`](examples/nft_transfers.py) — decode NFT transfer events (TEP-62)
- [`get_balance.py`](examples/get_balance.py) — fetch account TON balance
- [`backfill.py`](examples/backfill.py) — paginate all historical transactions
- [`export_to_sql.py`](examples/export_to_sql.py) — generate Postgres-compatible SQL dump

**0.4.0**
- [`failover_provider.py`](examples/failover_provider.py) — automatic primary/fallback provider switching
- [`async_redis_cache.py`](examples/async_redis_cache.py) — fully async Redis cache with `redis.asyncio`
- [`watch_multiple_addresses.py`](examples/watch_multiple_addresses.py) — watch several accounts in one loop
- [`retry_config.py`](examples/retry_config.py) — custom retry attempts and backoff

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

### `0.4.0` — current
- [x] Auto-retry with exponential backoff on `429` / `5xx` responses
- [x] `FailoverProvider` — automatic primary → fallback switching
- [x] `AsyncRedisCache` using `redis.asyncio` (no event-loop blocking)
- [x] WebSocket auto-reconnect with exponential backoff
- [x] `watch_addresses([addr1, addr2, ...])` — multi-address polling stream
- [x] `Balance(nano, ton)` dataclass — `get_balance()` returns both representations

### `0.3.0`
- [x] NFT transfer event decoding (TEP-62) — `extract_nft_transfers`, `decode_nft_transfer`
- [x] `get_balance()` — fetch account TON balance
- [x] `backfill_transactions()` — async generator for all historical transactions
- [x] SQL export helpers — `transactions_to_sql`, `jetton_transfers_to_sql` (Postgres-compatible)
- [x] CLI — `tonflow scan <address>`, `tonflow balance <address>`

### `0.2.0`
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

### `0.5.0` — planned
- [ ] DEX event decoding — Ston.fi swaps, DeDust liquidity events
- [ ] Staking / nominator pool event decoding
- [ ] Webhook sink (`stream_to_webhook(client, address, url)`)
- [ ] LiteServer provider (direct node connection, no API key)
- [ ] Prometheus metrics export

## License

MIT
