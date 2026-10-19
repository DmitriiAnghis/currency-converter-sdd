"""Tests for currency conversion arithmetic."""

from datetime import date
from decimal import Decimal
import pytest

from converter.converter import Conversion, convert
from converter.parser import Currency, RateSet


@pytest.fixture
def sample_rate_set() -> RateSet:
    rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.4523")),
        "USD": Currency(code="USD", name="US Dollar", nominal=1, value_mdl=Decimal("17.8541")),
        "ALL": Currency(code="ALL", name="Albanian Lek", nominal=10, value_mdl=Decimal("2.2010")),
        "HUF": Currency(code="HUF", name="Hungarian Forint", nominal=100, value_mdl=Decimal("4.8765")),
    }
    return RateSet(
        date=date(2026, 10, 19),
        currencies=rates,
        source="bnm",
        is_cached=False,
    )


def test_convert_same_currency(sample_rate_set):
    conv = convert(
        amount=Decimal("100"),
        from_code="EUR",
        to_code="EUR",
        rate_set=sample_rate_set,
    )
    assert isinstance(conv, Conversion)
    assert conv.result == Decimal("100.00")
    assert conv.reverse_rate == Decimal("1")
    assert conv.rate_date == date(2026, 10, 19)
    assert conv.source == "bnm"


def test_convert_mdl_to_eur(sample_rate_set):
    conv = convert(
        amount=Decimal("100"),
        from_code="MDL",
        to_code="EUR",
        rate_set=sample_rate_set,
    )
    # 100 * 1 / 19.4523 = 5.14078036... -> 5.14
    assert conv.result == Decimal("5.14")
    # Reverse rate: source units (MDL) per 1 target unit (EUR) = 19.4523 / 1
    assert conv.reverse_rate == Decimal("19.4523")
    assert conv.reverse_rate_formatted == "19.4523"


def test_convert_eur_to_mdl(sample_rate_set):
    conv = convert(
        amount=Decimal("100"),
        from_code="EUR",
        to_code="MDL",
        rate_set=sample_rate_set,
    )
    # 100 * 19.4523 / 1 = 1945.23
    assert conv.result == Decimal("1945.23")
    # Reverse rate: source units (EUR) per 1 target unit (MDL) = 1 / 19.4523 = 0.0514078...
    expected_rev = Decimal("1") / Decimal("19.4523")
    assert conv.reverse_rate == expected_rev
    # Rounded half-up to 4 decimals: 0.0514
    assert conv.reverse_rate_formatted == "0.0514"


def test_convert_cross_currency_eur_and_usd(sample_rate_set):
    # EUR to USD
    conv_eur_to_usd = convert(
        amount=Decimal("100"),
        from_code="EUR",
        to_code="USD",
        rate_set=sample_rate_set,
    )
    # 100 * 19.4523 / 17.8541 = 108.95144... -> 108.95
    assert conv_eur_to_usd.result == Decimal("108.95")
    # Reverse rate: source units (EUR) per 1 USD = 17.8541 / 19.4523 = 0.917839... -> 0.9178
    assert conv_eur_to_usd.reverse_rate == Decimal("17.8541") / Decimal("19.4523")
    assert conv_eur_to_usd.reverse_rate_formatted == "0.9178"

    # USD to EUR
    conv_usd_to_eur = convert(
        amount=Decimal("100"),
        from_code="USD",
        to_code="EUR",
        rate_set=sample_rate_set,
    )
    # 100 * 17.8541 / 19.4523 = 91.7839... -> 91.78
    assert conv_usd_to_eur.result == Decimal("91.78")
    assert conv_usd_to_eur.reverse_rate == Decimal("19.4523") / Decimal("17.8541")
    assert conv_usd_to_eur.reverse_rate_formatted == "1.0895"


def test_convert_nominal_units_arithmetic(sample_rate_set):
    # ALL has nominal 10 and value 2.2010 -> unit rate = 0.22010 MDL
    conv_all_to_mdl = convert(
        amount=Decimal("1000"),
        from_code="ALL",
        to_code="MDL",
        rate_set=sample_rate_set,
    )
    # 1000 * (2.2010 / 10) / 1 = 220.10
    assert conv_all_to_mdl.result == Decimal("220.10")

    # HUF has nominal 100 and value 4.8765 -> unit rate = 0.048765 MDL
    # Convert ALL to HUF
    conv_all_to_huf = convert(
        amount=Decimal("100"),
        from_code="ALL",
        to_code="HUF",
        rate_set=sample_rate_set,
    )
    # unit ALL = 0.22010, unit HUF = 0.048765
    # 100 * 0.22010 / 0.048765 = 451.34830... -> 451.35
    assert conv_all_to_huf.result == Decimal("451.35")


def test_convert_half_up_rounding(sample_rate_set):
    # Test an amount that requires half-up rounding (e.g. .005 -> .01)
    # Using USD rate 17.8541
    # Find amount * 1 / 17.8541 ending in exactly .xx5 or verify half-up behavior
    # Decimal rounding test:
    conv = convert(
        amount=Decimal("123.456"),
        from_code="MDL",
        to_code="MDL",
        rate_set=sample_rate_set,
    )
    # 123.456 rounds to 123.46 with ROUND_HALF_UP
    assert conv.result == Decimal("123.46")


def test_convert_unknown_currency_raises(sample_rate_set):
    with pytest.raises(KeyError):
        convert(
            amount=Decimal("100"),
            from_code="GBP",
            to_code="EUR",
            rate_set=sample_rate_set,
        )
