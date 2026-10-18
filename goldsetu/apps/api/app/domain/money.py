"""Money helpers: public inputs are rupees as decimal text/Decimal; storage is paise."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

PAISE_PER_RUPEE = Decimal("100")
CENT = Decimal("0.01")


def decimal_value(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("binary floating-point money is forbidden")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("money must be a finite decimal") from exc
    if not amount.is_finite():
        raise ValueError("money must be finite")
    return amount


def rupees_to_paise(value: Any) -> int:
    amount = decimal_value(value)
    if amount < 0:
        raise ValueError("money cannot be negative")
    rounded = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return int(rounded * PAISE_PER_RUPEE)


def metal_value_paise(weight_g: Any, rate_paise_per_gram: int) -> int:
    weight = decimal_value(weight_g)
    if weight < 0 or rate_paise_per_gram < 0:
        raise ValueError("weight and rate cannot be negative")
    return int((weight * Decimal(rate_paise_per_gram)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> Decimal:
    if not isinstance(paise, int) or isinstance(paise, bool) or paise < 0:
        raise ValueError("paise must be a non-negative integer")
    return (Decimal(paise) / PAISE_PER_RUPEE).quantize(CENT)
