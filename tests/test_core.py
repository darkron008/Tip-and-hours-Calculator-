from decimal import Decimal
import pytest

from calculator.core import calculate_tip, calculate_total, calculate_pay


@pytest.mark.parametrize(
    "amount,percent,expected",
    [
        (Decimal("100"), Decimal("15"), Decimal("15.00")),
        (Decimal("0"), Decimal("20"), Decimal("0.00")),
        # small percent resulting in half-cent -> should round HALF_UP to 0.01
        (Decimal("1"), Decimal("0.5"), Decimal("0.01")),
    ],
)
def test_calculate_tip(amount, percent, expected):
    assert calculate_tip(amount, percent) == expected


def test_calculate_total_basic():
    assert calculate_total(Decimal("100"), Decimal("15")) == Decimal("115.00")


@pytest.mark.parametrize(
    "hours,rate,expected",
    [
        (Decimal("40"), Decimal("15.5"), Decimal("620.00")),
        (Decimal("0"), Decimal("100"), Decimal("0.00")),
        (Decimal("2.345"), Decimal("10"), Decimal("23.45")),
    ],
)
def test_calculate_pay(hours, rate, expected):
    assert calculate_pay(hours, rate) == expected


def test_negative_values_raise():
    with pytest.raises(ValueError):
        calculate_tip(Decimal("-1"), Decimal("10"))
    with pytest.raises(ValueError):
        calculate_tip(Decimal("10"), Decimal("-5"))
    with pytest.raises(ValueError):
        calculate_pay(Decimal("-2"), Decimal("10"))


def test_accepts_floats_and_strings():
    # ensure function accepts floats/strings and returns Decimal rounded
    assert calculate_tip(100, 15) == Decimal("15.00")
    assert calculate_tip("10", "0.5") == Decimal("0.05")
