# tonflow

Python toolkit for reading, decoding, normalizing, and locally caching TON blockchain data.

`tonflow` is designed as a lightweight MIT-licensed library. It does not run a hosted indexer and does not store blockchain data on behalf of users. Any cache or database integration lives on the user's machine or infrastructure.

## Goals

- Read TON account transactions through pluggable API clients.
- Normalize transactions, messages, and Jetton transfer events into Python models.
- Cache repeated reads locally to reduce pressure on public nodes.
- Stream new address events through polling first, with websocket support later.

## Non-goals

- No hosted backend operated by the maintainers.
- No centralized storage of user or blockchain data.
- No paid cloud dependency required to use the open source package.

## Development status

Pre-alpha. The package scaffold is in place; network adapters and real Jetton decoding are planned next.

## Local development

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## License

MIT
