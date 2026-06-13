import pytest

from tonflow import is_user_friendly_address, normalize_address


def test_normalize_address_trims_whitespace() -> None:
    assert normalize_address("  EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA  ") == (
        "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    )


def test_normalize_address_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_address("   ")


def test_is_user_friendly_address_checks_shape() -> None:
    assert is_user_friendly_address("EQ" + "A" * 46)
    assert not is_user_friendly_address("short")
