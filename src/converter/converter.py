"""Currency conversion logic using exact Decimal arithmetic."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from converter.parser import RateSet


@dataclass(frozen=True)
class Conversion:
    """Represents a completed conversion calculation."""
    amount: Decimal
    from_code: str
    to_code: str
    result: Decimal
    reverse_rate: Decimal
    rate_date: date
    source: str

    @property
    def result_formatted(self) -> str:
        """Result formatted to two decimal places."""
        return f"{self.result:.2f}"

    @property
    def reverse_rate_formatted(self) -> str:
        """Reverse rate rounded to four decimal places using half-up rule."""
        quantized = self.reverse_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return f"{quantized:.4f}"


def convert(
    amount: Decimal,
    from_code: str,
    to_code: str,
    rate_set: RateSet,
) -> Conversion:
    """Convert an amount from one currency to another using the provided RateSet.

    Args:
        amount: Positive Decimal amount to convert.
        from_code: Currency code to convert from.
        to_code: Currency code to convert to.
        rate_set: Set of rates containing both currencies.

    Returns:
        Conversion object with converted result and reverse rate.

    Raises:
        KeyError: If from_code or to_code is not present in rate_set.
    """
    if from_code not in rate_set.currencies:
        raise KeyError(f"Currency code '{from_code}' not found in rate set for {rate_set.date}")
    if to_code not in rate_set.currencies:
        raise KeyError(f"Currency code '{to_code}' not found in rate set for {rate_set.date}")

    if from_code == to_code:
        result = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        reverse_rate = Decimal("1")
    else:
        source_curr = rate_set.currencies[from_code]
        target_curr = rate_set.currencies[to_code]

        source_unit_rate = source_curr.unit_rate_mdl
        target_unit_rate = target_curr.unit_rate_mdl

        raw_result = amount * source_unit_rate / target_unit_rate
        result = raw_result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        reverse_rate = target_unit_rate / source_unit_rate

    return Conversion(
        amount=amount,
        from_code=from_code,
        to_code=to_code,
        result=result,
        reverse_rate=reverse_rate,
        rate_date=rate_set.date,
        source=rate_set.source,
    )
