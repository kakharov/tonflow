"""Address helpers for TON account identifiers."""

USER_FRIENDLY_PREFIXES = ("EQ", "UQ", "kQ", "0Q")


def normalize_address(address: str) -> str:
    """Return a trimmed TON address string.

    The first MVP keeps address handling deliberately conservative. Full checksum
    validation and raw/user-friendly conversion will be added once the TON cell
    tooling is selected.
    """

    normalized = address.strip()
    if not normalized:
        msg = "TON address cannot be empty."
        raise ValueError(msg)
    return normalized


def is_user_friendly_address(address: str) -> bool:
    """Return whether the value looks like a TON user-friendly address."""

    normalized = normalize_address(address)
    return len(normalized) == 48 and normalized.startswith(USER_FRIENDLY_PREFIXES)
