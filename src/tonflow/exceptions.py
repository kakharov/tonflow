"""Custom exceptions raised by tonflow."""


class TonflowError(Exception):
    """Base error for tonflow."""


class TonflowAPIError(TonflowError):
    """Raised when an upstream TON API request fails."""


class TonflowDecodeError(TonflowError):
    """Raised when blockchain payload decoding fails."""
