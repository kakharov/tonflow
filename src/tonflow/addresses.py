"""Address helpers for TON account identifiers."""

from __future__ import annotations

import base64
import re

# User-friendly address: 48 base64url chars, first byte encodes workchain + flags.
# EQ = bounceable mainnet (workchain 0)
# UQ = non-bounceable mainnet (workchain 0)
# kQ = bounceable testnet (workchain 0)
# 0Q = non-bounceable testnet (workchain 0)
_USER_FRIENDLY_PREFIXES = ("EQ", "UQ", "kQ", "0Q")
_USER_FRIENDLY_LENGTH = 48
_USER_FRIENDLY_RE = re.compile(r"^[A-Za-z0-9_\-]{48}$")

# Raw address: "<workchain>:<64 hex chars>"
_RAW_RE = re.compile(r"^-?[0-9]+:[0-9a-fA-F]{64}$")


def normalize_address(address: str) -> str:
    """Return the trimmed TON address, raising ValueError if blank."""
    normalized = address.strip()
    if not normalized:
        raise ValueError("TON address cannot be empty.")
    return normalized


def is_user_friendly_address(address: str) -> bool:
    """Return True if *address* looks like a valid TON user-friendly address.

    Checks:
    - length is exactly 48 characters
    - characters are valid base64url (A-Z, a-z, 0-9, ``-``, ``_``)
    - starts with a known workchain prefix (EQ, UQ, kQ, 0Q)
    - base64-decoded payload is exactly 36 bytes (tag + workchain + hash + crc)
    """
    addr = address.strip()
    if len(addr) != _USER_FRIENDLY_LENGTH:
        return False
    if not addr.startswith(_USER_FRIENDLY_PREFIXES):
        return False
    if not _USER_FRIENDLY_RE.match(addr):
        return False
    try:
        decoded = base64.urlsafe_b64decode(addr + "==")
    except Exception:
        return False
    return len(decoded) == 36


def is_raw_address(address: str) -> bool:
    """Return True if *address* is a TON raw address (``workchain:hex``)."""
    return bool(_RAW_RE.match(address.strip()))


def validate_address(address: str) -> str:
    """Return the trimmed address if it is a recognized TON format.

    Raises:
        ValueError: if the address is neither user-friendly nor raw.
    """
    addr = normalize_address(address)
    if is_user_friendly_address(addr) or is_raw_address(addr):
        return addr
    raise ValueError(
        f"'{addr}' is not a valid TON address. "
        "Expected a 48-char user-friendly address (EQ/UQ/kQ/0Q...) "
        "or a raw address (workchain:64hexchars)."
    )
