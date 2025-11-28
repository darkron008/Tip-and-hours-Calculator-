from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def calculate_tip(amount, percent) -> Decimal:
    """Return the tip amount for `amount` at `percent` percent.

    Rounds to cents using ROUND_HALF_UP.
    """
    a = _to_decimal(amount)
    p = _to_decimal(percent)
    if a < 0 or p < 0:
        raise ValueError("amount and percent must be non-negative")
    tip = (a * p / Decimal("100"))
    return tip.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_total(amount, percent) -> Decimal:
    """Return amount + tip, rounded to cents."""
    a = _to_decimal(amount)
    return (a + calculate_tip(a, percent)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_pay(hours, rate) -> Decimal:
    """Return gross pay for `hours` at `rate` per hour, rounded to cents."""
    h = _to_decimal(hours)
    r = _to_decimal(rate)
    if h < 0 or r < 0:
        raise ValueError("hours and rate must be non-negative")
    pay = h * r
    return pay.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
