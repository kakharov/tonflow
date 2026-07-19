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
<summary><strong>0.4.0</strong> — Async Redis, multi-address watch, retry, TON DNS <em>(planned)</em></summary>

- Async Redis cache (`redis.asyncio`) — replaces sync client that blocks the event loop
- `watch_addresses([addr1, addr2, ...])` — watch multiple accounts simultaneously
- Auto-retry with exponential backoff on transient API errors
- TON DNS resolution: `resolve_domain("example.ton")` → raw address
- Built-in rate limiter in providers to avoid 429s on public endpoints

</details>

---

<details>
<summary><strong>0.3.0</strong> — NFT decoding, balance, backfill, Postgres, CLI <em>(planned)</em></summary>

- NFT transfer event decoding (TEP-62)
- `get_balance()` — fetch account TON balance
- Backfill utility — paginate the full transaction history for an address
- Postgres export helper
- CLI: `tonflow scan <address>`

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
    boc,                        # base64-encoded signed BOC
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
