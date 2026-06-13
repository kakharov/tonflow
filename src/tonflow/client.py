"""Client entry points for reading TON blockchain data."""

from __future__ import annotations

from dataclasses import dataclass

from tonflow.addresses import normalize_address
from tonflow.models import Transaction


@dataclass(slots=True)
class TonClient:
    """High-level TON API client.

    Network methods are intentionally thin in the scaffold. The next patch will
    add an async HTTP transport and a concrete transactions endpoint adapter.
    """

    endpoint: str
    api_key: str | None = None

    async def get_transactions(self, address: str, *, limit: int = 20) -> list[Transaction]:
        normalized = normalize_address(address)
        if limit <= 0:
            msg = "limit must be greater than zero."
            raise ValueError(msg)
        raise NotImplementedError(f"Transaction fetching is not implemented yet for {normalized}.")
