"""Tests for TON address helpers."""

import pytest

from tonflow import is_user_friendly_address, normalize_address
from tonflow.addresses import is_raw_address, validate_address

# A real-looking user-friendly address (48 base64url chars, EQ prefix).
VALID_EQ = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
VALID_UQ = "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
VALID_KQ = "kQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
VALID_0Q = "0QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

VALID_RAW = "0:" + "a" * 64
VALID_RAW_MINUS = "-1:" + "b" * 64

# ---------------------------------------------------------------------------
# normalize_address
# ---------------------------------------------------------------------------


def test_normalize_address_trims_whitespace() -> None:
    assert normalize_address(f"  {VALID_EQ}  ") == VALID_EQ


def test_normalize_address_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_address("")


def test_normalize_address_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_address("   ")


# ---------------------------------------------------------------------------
# is_user_friendly_address
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("addr", [VALID_EQ, VALID_UQ, VALID_KQ, VALID_0Q])
def test_is_user_friendly_accepts_known_prefixes(addr: str) -> None:
    assert is_user_friendly_address(addr) is True


def test_is_user_friendly_rejects_short_address() -> None:
    assert is_user_friendly_address("EQ" + "A" * 10) is False


def test_is_user_friendly_rejects_unknown_prefix() -> None:
    assert is_user_friendly_address("ZZ" + "A" * 46) is False


def test_is_user_friendly_rejects_raw_address() -> None:
    assert is_user_friendly_address(VALID_RAW) is False


def test_is_user_friendly_rejects_empty() -> None:
    assert is_user_friendly_address("") is False


def test_is_user_friendly_rejects_invalid_base64_chars() -> None:
    # '@' is not valid base64url
    assert is_user_friendly_address("EQ" + "@" * 46) is False


# ---------------------------------------------------------------------------
# is_raw_address
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("addr", [VALID_RAW, VALID_RAW_MINUS, "0:" + "0" * 64])
def test_is_raw_address_accepts_valid(addr: str) -> None:
    assert is_raw_address(addr) is True


def test_is_raw_address_rejects_short_hex() -> None:
    assert is_raw_address("0:" + "a" * 10) is False


def test_is_raw_address_rejects_user_friendly() -> None:
    assert is_raw_address(VALID_EQ) is False


def test_is_raw_address_rejects_missing_colon() -> None:
    assert is_raw_address("0" + "a" * 64) is False


def test_is_raw_address_rejects_non_hex() -> None:
    assert is_raw_address("0:" + "z" * 64) is False


# ---------------------------------------------------------------------------
# validate_address
# ---------------------------------------------------------------------------


def test_validate_address_accepts_user_friendly() -> None:
    assert validate_address(VALID_EQ) == VALID_EQ


def test_validate_address_accepts_raw() -> None:
    assert validate_address(VALID_RAW) == VALID_RAW


def test_validate_address_trims_whitespace() -> None:
    assert validate_address(f"  {VALID_EQ}  ") == VALID_EQ


def test_validate_address_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a valid TON address"):
        validate_address("not-an-address")


def test_validate_address_rejects_empty() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_address("   ")
