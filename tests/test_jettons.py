from decimal import Decimal

from tonflow.jettons import normalize_amount


def test_normalize_amount_uses_decimals() -> None:
    assert normalize_amount(123456789, 6) == Decimal("123.456789")
