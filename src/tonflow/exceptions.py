"""Custom exceptions raised by tonflow."""

from __future__ import annotations


class TonflowError(Exception):
    """Base error for tonflow."""


class TonflowAPIError(TonflowError):
    """Raised when an upstream TON API request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class TonflowDecodeError(TonflowError):
    """Raised when blockchain payload decoding fails."""


class TonflowTimeoutError(TonflowError):
    """Raised when send_and_confirm does not see a confirmation within the timeout."""


class TonflowExpiredError(TonflowError):
    """Raised when valid_until passes before the transaction is confirmed.

    The transaction will never be included in a block — a new message with an
    updated seqno and valid_until must be built and signed before retrying.
    """
