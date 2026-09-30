# Changelog

---

<details>
<summary><strong>0.5.0</strong> — DEX events, Webhook sink, LiteServer provider <em>(planned)</em></summary>

- DEX event decoding — Ston.fi swaps and DeDust liquidity events
- Staking / nominator pool event decoding
- Webhook sink: push new transactions to an HTTP endpoint
- LiteServer provider — direct node connection, no API key required
- Prometheus metrics export

</details>

---

<details>
<summary><strong>0.4.0</strong> — Retry, failover, async Redis, WS reconnect, watch_addresses</summary>

### Added

**Auto-retry with exponential backoff**

Both `TonAPIProvider` and `TonCenterProvider` now retry automatically on `429`,
`500`, `502`, `503`, and `504` responses. The delay doubles each attempt
(`backoff * 2^attempt`) with a small random jitter to avoid thundering herd.

```python
from tonflow.providers import TonAPIProvider
from tonflow import TonClient

# 5 attempts, starting at 1 s backoff
provider = TonAPIProvider(api_key="...", retry_attempts=5, retry_backoff=1.0)
client = TonClient(provider=provider)
```

Default: `retry_attempts=3`, `retry_backoff=0.5`.

**`FailoverProvider`**

Wraps two providers — tries the primary, automatically switches to the fallback
on any `TonflowAPIError`.

```python
from tonflow import TonClient
from tonflow.providers import FailoverProvider, TonAPIProvider, TonCenterProvider

provider = FailoverProvider(
    TonAPIProvider(api_key="tonapi-key"),
    TonCenterProvider(api_key="toncenter-key"),
)
client = TonClient(provider=provider)
```

**`AsyncRedisCache`** (`pip install tonflow[redis]`)

Fully async Redis cache using `redis.asyncio`. Eliminates the event-loop
blocking that `RedisCache` (sync) causes in long-running services.

```python
import redis.asyncio as aioredis
from tonflow import TonClient, AsyncRedisCache

r = aioredis.Redis(host="localhost", port=6379, db=0)
cache = AsyncRedisCache(r, prefix="myapp:")
client = TonClient(cache=cache, cache_ttl_seconds=30)
```

`TonClient` detects the async backend automatically — no other changes needed.

**WebSocket auto-reconnect**

`stream_transactions_ws` now reconnects automatically after a dropped connection
with exponential backoff (1 s → 2 s → 4 s … up to 60 s).
Pass `reconnect=False` to raise immediately on disconnect (old behaviour).

```python
from tonflow.websocket import stream_transactions_ws

# Runs indefinitely, reconnects transparently on network hiccups
async for tx in stream_transactions_ws(client, "EQ...", api_key="...", reconnect=True):
    process(tx)
```

**`watch_addresses`**

Watch multiple addresses concurrently in a single `async for` loop.
Events from all addresses are merged as they arrive.

```python
from tonflow import watch_addresses

async for tx in watch_addresses(client, ["EQ...", "UQ...", "EQ2..."]):
    print(tx.account, tx.hash)
```

**`Balance` dataclass**

`get_balance()` now returns a `Balance` object instead of a plain `int`,
preserving the raw nanoton value without float precision loss.

```python
b = await client.get_balance("EQ...")
print(f"{b.ton:.9f} TON  ({b.nano} nanotons)")
```

### Changed

- `get_balance()` return type: `int` → `Balance(nano: int, ton: Decimal)`
- `TonAPIProvider` / `TonCenterProvider`: new `retry_attempts` and `retry_backoff` kwargs
- `stream_transactions_ws`: new `reconnect` kwarg (default `True`)

</details>

---

<details>
<summary><strong>0.3.0</strong> — NFT decoding, balance, backfill, SQL export, CLI</summary>

### Added

**NFT transfer event decoding** (TEP-62)

Decode NFT ownership transfers from raw transactions.

```python
from tonflow import extract_nft_transfers

transfers = extract_nft_transfers(tx, nft_collection="EQcollection...")
for t in transfers:
    print(t.sender, "→", t.recipient, t.nft_address)
```

New model: `NftTransfer` (`transaction_hash`, `sender`, `recipient`, `nft_address`, `nft_collection`, `comment`).

**`get_balance()`**

Fetch an account's TON balance in nanotons without caching.

```python
nanotons = await client.get_balance("EQ...")
print(f"{nanotons / 1e9:.9f} TON")
```

**`backfill_transactions()`**

Async generator that paginates through all historical transactions, bypassing the cache.

```python
from tonflow import backfill_transactions

async for tx in backfill_transactions(client, "EQ...", page_size=100):
    store(tx)
```

Accepts `stop_before_lt` to resume from a known checkpoint.

**SQL export helpers**

Generate Postgres-compatible SQL with idempotent `INSERT … ON CONFLICT (hash) DO NOTHING`.

```python
from tonflow import transactions_to_sql, jetton_transfers_to_sql

sql = transactions_to_sql(txs)  # includes CREATE TABLE IF NOT EXISTS
with open("dump.sql", "w") as f:
    f.write(sql)
```

**CLI**

```bash
tonflow scan EQ...           # print recent transactions
tonflow balance EQ...        # print account balance
tonflow scan EQ... --provider toncenter --api-key KEY
```

</details>

---

<details>
<summary><strong>0.2.0</strong> — Providers, WebSocket, Redis, send_and_confirm</summary>

### Added

**Pluggable provider system**

New `Provider` protocol lets you swap the underlying API without touching application code.
`TonAPIProvider` is the default; `TonCenterProvider` is now included out of the box.

```python
from tonflow import TonClient, TonCenterProvider

client = TonClient(provider=TonCenterProvider(api_key="your-key"))
```

**`send_and_confirm()`**

Broadcasts a pre-signed BOC and polls until the transaction is confirmed on-chain.
Raises `TonflowTimeoutError` if the timeout elapses, or `TonflowExpiredError` if
`valid_until` passes before confirmation.

```python
from tonflow import send_and_confirm

tx = await send_and_confirm(
    client,
    wallet_address,
    boc,  # base64-encoded signed BOC
    timeout=60,
    valid_until=int(time()) + 60,
)
print("confirmed:", tx.hash, tx.logical_time)
```

**WebSocket streaming** (`pip install tonflow[ws]`)

Push-based real-time streaming via TonAPI WebSocket. Lower latency than polling.

```python
from tonflow.websocket import stream_transactions_ws

async for tx in stream_transactions_ws(client, "EQ...", api_key="..."):
    print(tx.hash, tx.logical_time)
```

**Redis cache adapter** (`pip install tonflow[redis]`)

Production-grade cache backend for services that already run Redis.

```python
import redis
from tonflow import TonClient, RedisCache

cache = RedisCache(redis.Redis(host="localhost"), prefix="myapp:")
client = TonClient(endpoint="https://tonapi.io", cache=cache, cache_ttl_seconds=30)
```

**Jetton burn and mint decoding** (TEP-74)

```python
from tonflow import extract_jetton_burns, extract_jetton_mints

burns = extract_jetton_burns(tx, decimals=9, symbol="JETTON")
mints = extract_jetton_mints(tx, decimals=9, symbol="JETTON")
```

New models: `JettonBurn`, `JettonMint`.

**New exceptions**

| Exception | Raised when |
|---|---|
| `TonflowTimeoutError` | `send_and_confirm` timeout elapsed |
| `TonflowExpiredError` | `valid_until` passed before confirmation |

</details>

---

<details>
<summary><strong>0.1.0</strong> — Initial release</summary>

### Added

- `TonClient` with `get_transactions()` and `get_jetton_transfers()`
- TEP-74 Jetton transfer decoding (`decode_jetton_transfer`, `extract_jetton_transfers`)
- `SQLiteCache` and `InMemoryCache` with per-entry TTL
- `watch_address()` — long-polling async generator for real-time transaction streaming
- Address validation: `validate_address`, `is_user_friendly_address`, `is_raw_address`, `normalize_address`
- JSON and CSV export: `transactions_to_json`, `transactions_to_csv`, `jetton_transfers_to_json`, `jetton_transfers_to_csv`
- `TonflowAPIError`, `TonflowDecodeError` exceptions
- Models: `Transaction`, `Message`, `JettonTransfer`, `MessageDirection`, `TransactionStatus`

</details>
