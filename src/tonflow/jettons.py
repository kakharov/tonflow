"""Jetton event normalization helpers."""

from decimal import Decimal


def normalize_amount(raw_amount: int | str, decimals: int) -> Decimal:
    """Convert a raw Jetton amount into a human-readable decimal value."""

    amount = Decimal(str(raw_amount))
    scale = Decimal(10) ** decimals
    return amount / scale
