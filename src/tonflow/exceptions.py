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
