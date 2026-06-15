# tonflow

Python toolkit for reading, decoding, normalizing, and locally caching TON blockchain data.

`tonflow` is a lightweight MIT-licensed library. It does not run a hosted indexer and does not store blockchain data on your behalf — any cache lives on your own machine or infrastructure.

## Install

```bash
pip install tonflow
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

### Stream new transactions in real time

```python
from tonflow import watch_address

async for tx in watch_address(client, "EQ...", interval_seconds=5):
    print("new tx:", tx.hash, tx.logical_time)
```

### Cache responses locally (avoid hammering public nodes)

```python
from tonflow import SQLiteCache, TonClient

client = TonClient(
    endpoint="https://tonapi.io",
    cache=SQLiteCache(".tonflow/cache.sqlite3"),
    cache_ttl_seconds=60,
)
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

validate_address("EQ...")        # raises ValueError if invalid
is_user_friendly_address("EQ...") # True / False
is_raw_address("0:abcd...")        # True / False
```

## API reference

### `TonClient`

```python
TonClient(
    endpoint: str,
    api_key: str | None = None,
    timeout: float = 10.0,
    cache: JSONCache | None = None,
    cache_ttl_seconds: float | None = 30.0,
)
```

| Method | Description |
|---|---|
| `get_transactions(address, limit, before_lt)` | Fetch and normalize account transactions |
| `get_jetton_transfers(address, limit, before_lt, decimals, jetton_minter, symbol)` | Fetch transactions and return only Jetton transfer events |
| `aclose()` | Close the underlying HTTP client |

Use as an async context manager (`async with`) for automatic cleanup.

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

### Models

| Model | Key fields |
|---|---|
| `Transaction` | `hash`, `account`, `logical_time`, `timestamp`, `status`, `in_message`, `out_messages`, `total_fees` |
| `Message` | `source`, `destination`, `direction`, `value`, `body`, `op_code` |
| `JettonTransfer` | `transaction_hash`, `sender`, `recipient`, `amount`, `raw_amount`, `decimals`, `symbol`, `jetton_wallet`, `jetton_minter`, `comment` |

### Cache backends

| Class | Storage | Best for |
|---|---|---|
| `InMemoryCache` | In-process dict | Tests, short-lived scripts |
| `SQLiteCache(path)` | SQLite file on disk | Local scripts, small services |

Both implement the `JSONCache` protocol — you can write your own backend (e.g. Redis) by implementing `get`, `set`, and `clear`.

### Export helpers

| Function | Output |
|---|---|
| `transactions_to_json(txs, indent=None)` | JSON string |
| `transactions_to_csv(txs)` | CSV string |
| `jetton_transfers_to_json(transfers, indent=None)` | JSON string |
| `jetton_transfers_to_csv(transfers)` | CSV string |

`Decimal` amounts are serialized as strings in both formats to preserve precision.

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

## Examples

See the [`examples/`](examples/) directory:

- [`get_transactions.py`](examples/get_transactions.py) — fetch and print recent transactions
- [`get_jetton_transfers.py`](examples/get_jetton_transfers.py) — fetch and print Jetton transfers
- [`watch_address.py`](examples/watch_address.py) — stream new transactions in real time
- [`export_to_csv.py`](examples/export_to_csv.py) — save transactions and transfers to CSV
- [`cache_with_sqlite.py`](examples/cache_with_sqlite.py) — local SQLite cache in action

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

## License

MIT
