"""Validation for monetary amounts and user inputs."""

from decimal import Decimal, InvalidOperation
import re


class ValidationError(ValueError):
    """Raised when user input fails validation."""
    pass


_VALID_DECIMAL_PATTERN = re.compile(r"^\d+(?:[.,]\d+)?$")


def parse_amount(value: str) -> Decimal:
    """Parse and validate a monetary amount string into a positive Decimal.

    Accepts a string representation of a positive decimal using either a single
    comma or a single period as the decimal separator. Grouping separators,
    multiple separators, mixed separators, negative numbers, zero, and
    non-numeric characters are rejected with ValidationError.
    """
    if not isinstance(value, str):
        raise ValidationError("Amount must be a string.")

    stripped = value.strip()
    if not stripped:
        raise ValidationError("Amount cannot be empty.")

    if not _VALID_DECIMAL_PATTERN.fullmatch(stripped):
        if stripped.startswith("-"):
            raise ValidationError("Amount must be positive.")
        if "," in stripped and "." in stripped:
            raise ValidationError("Amount cannot contain both comma and period separators.")
        if stripped.count(",") > 1 or stripped.count(".") > 1:
            raise ValidationError("Amount cannot contain multiple decimal separators.")
        raise ValidationError("Amount must be a valid positive number.")

    normalized = stripped.replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValidationError("Amount is not a valid number.") from exc

    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")

    return amount
