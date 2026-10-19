"""Tests for amount validation and parsing."""

from decimal import Decimal
import pytest

from converter.validation import ValidationError, parse_amount


def test_parse_amount_valid_period_decimal():
    assert parse_amount("100.50") == Decimal("100.50")
    assert parse_amount("1") == Decimal("1")
    assert parse_amount("0.01") == Decimal("0.01")
    assert parse_amount("12345.6789") == Decimal("12345.6789")


def test_parse_amount_valid_comma_decimal():
    assert parse_amount("100,50") == Decimal("100.50")
    assert parse_amount("0,01") == Decimal("0.01")
    assert parse_amount("12345,6789") == Decimal("12345.6789")


def test_parse_amount_with_whitespace():
    assert parse_amount("  100.50  ") == Decimal("100.50")
    assert parse_amount(" 42,75 ") == Decimal("42.75")


@pytest.mark.parametrize("empty_input", ["", "   ", "\t", "\n"])
def test_parse_amount_empty_raises(empty_input):
    with pytest.raises(ValidationError, match="empty"):
        parse_amount(empty_input)


@pytest.mark.parametrize("zero_input", ["0", "0.0", "0,00", "00", "0.0000"])
def test_parse_amount_zero_raises(zero_input):
    with pytest.raises(ValidationError, match="greater than zero"):
        parse_amount(zero_input)


@pytest.mark.parametrize("negative_input", ["-1", "-0.01", "-10,50", "-500"])
def test_parse_amount_negative_raises(negative_input):
    with pytest.raises(ValidationError):
        parse_amount(negative_input)


@pytest.mark.parametrize(
    "invalid_input",
    [
        "abc",
        "12a3",
        "$100",
        "100€",
        "100 MDL",
        "1 000",
        "1e5",
        "1E-2",
        "+50",
    ],
)
def test_parse_amount_alphabetic_and_non_numeric_raises(invalid_input):
    with pytest.raises(ValidationError):
        parse_amount(invalid_input)


@pytest.mark.parametrize(
    "malformed_input",
    [
        "1.2.3",
        "1,2,3",
        "1..5",
        "1,,5",
        "1,234.50",
        "1.234,50",
        ".",
        ",",
        "+-5",
    ],
)
def test_parse_amount_malformed_and_mixed_separators_raises(malformed_input):
    with pytest.raises(ValidationError):
        parse_amount(malformed_input)


def test_form_enables_conversion_only_when_all_fields_filled():
    import tkinter as tk
    from converter.gui import ConverterApp

    root = tk.Tk()
    try:
        root.withdraw()
        app = ConverterApp(root)

        # Initially, amount is empty, currencies are unselected -> disabled
        assert app.convert_button.instate(["disabled"])

        # Set amount only -> still disabled
        app.amount_var.set("100")
        assert app.convert_button.instate(["disabled"])

        # Set from currency -> still disabled
        app.from_currency_var.set("EUR")
        assert app.convert_button.instate(["disabled"])

        # Set to currency -> now enabled
        app.to_currency_var.set("MDL")
        assert not app.convert_button.instate(["disabled"])

        # Clear amount -> becomes disabled again
        app.amount_var.set("")
        assert app.convert_button.instate(["disabled"])
    finally:
        root.destroy()


def test_form_shows_validation_error_on_invalid_amount():
    import tkinter as tk
    from converter.gui import ConverterApp

    root = tk.Tk()
    try:
        root.withdraw()
        app = ConverterApp(root)
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")

        # Set invalid amount (zero)
        app.amount_var.set("0")
        assert not app.convert_button.instate(["disabled"])
        app._on_convert_clicked()

        assert app.validation_error_var.get() != ""
        assert "greater than zero" in app.validation_error_var.get()

        # Correct amount to valid positive number
        app.amount_var.set("100.50")
        app._on_convert_clicked()
        assert app.validation_error_var.get() == ""
    finally:
        root.destroy()

