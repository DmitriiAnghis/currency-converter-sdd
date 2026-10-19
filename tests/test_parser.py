"""Tests for BNM XML parser."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest

from converter.parser import (
    Currency,
    EmptyResponse,
    InvalidResponse,
    RateSet,
    parse_bnm_xml,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bnm_rates.xml"


def test_parse_bnm_xml_fixture():
    xml_content = FIXTURE_PATH.read_text(encoding="utf-8")
    rate_set = parse_bnm_xml(xml_content)

    assert isinstance(rate_set, RateSet)
    assert rate_set.date == date(2026, 10, 19)
    assert rate_set.source == "bnm"
    assert rate_set.is_cached is False

    # Check currencies
    assert "EUR" in rate_set.currencies
    assert "USD" in rate_set.currencies
    assert "MDL" in rate_set.currencies
    assert "ALL" in rate_set.currencies

    # Check EUR
    eur = rate_set.currencies["EUR"]
    assert eur.code == "EUR"
    assert eur.name == "Euro"
    assert eur.nominal == 1
    assert eur.value_mdl == Decimal("19.4523")
    assert eur.unit_rate_mdl == Decimal("19.4523")

    # Check ALL (nominal 10)
    all_curr = rate_set.currencies["ALL"]
    assert all_curr.nominal == 10
    assert all_curr.value_mdl == Decimal("2.2010")
    assert all_curr.unit_rate_mdl == Decimal("2.2010") / Decimal(10)

    # Check MDL base currency
    mdl = rate_set.currencies["MDL"]
    assert mdl.nominal == 1
    assert mdl.value_mdl == Decimal("1")
    assert mdl.unit_rate_mdl == Decimal("1")


def test_parse_bnm_xml_preserves_decimal_precision():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="01.01.2026" name="Official exchange rate">
        <Valute ID="1">
            <CharCode>XYZ</CharCode>
            <Nominal>1</Nominal>
            <Name>Precise Currency</Name>
            <Value>12.34567890123456789</Value>
        </Valute>
    </ValCurs>"""
    rate_set = parse_bnm_xml(xml)
    assert rate_set.currencies["XYZ"].value_mdl == Decimal("12.34567890123456789")


def test_parse_bnm_xml_empty_response():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
    </ValCurs>"""
    with pytest.raises(EmptyResponse):
        parse_bnm_xml(xml)


@pytest.mark.parametrize(
    "malformed_xml",
    [
        "not xml at all",
        "<unclosed>tag",
        "<WrongRoot Date='19.10.2026'></WrongRoot>",
        "<ValCurs></ValCurs>",  # missing Date attribute
        "<ValCurs Date='invalid-date'><Valute><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>20</Value></Valute></ValCurs>",
    ],
)
def test_parse_bnm_xml_malformed_xml_raises_invalid_response(malformed_xml):
    with pytest.raises(InvalidResponse):
        parse_bnm_xml(malformed_xml)


def test_parse_bnm_xml_duplicate_char_code_raises_invalid_response():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
        <Valute ID="1">
            <CharCode>EUR</CharCode>
            <Nominal>1</Nominal>
            <Name>Euro 1</Name>
            <Value>20.0000</Value>
        </Valute>
        <Valute ID="2">
            <CharCode>EUR</CharCode>
            <Nominal>1</Nominal>
            <Name>Euro 2</Name>
            <Value>20.5000</Value>
        </Valute>
    </ValCurs>"""
    with pytest.raises(InvalidResponse, match="[Dd]uplicate"):
        parse_bnm_xml(xml)


@pytest.mark.parametrize(
    "valute_snippet",
    [
        # Missing CharCode
        "<Nominal>1</Nominal><Name>Euro</Name><Value>20.0000</Value>",
        # Missing Name
        "<CharCode>EUR</CharCode><Nominal>1</Nominal><Value>20.0000</Value>",
        # Missing Nominal
        "<CharCode>EUR</CharCode><Name>Euro</Name><Value>20.0000</Value>",
        # Missing Value
        "<CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name>",
        # Negative Nominal
        "<CharCode>EUR</CharCode><Nominal>-1</Nominal><Name>Euro</Name><Value>20.0000</Value>",
        # Zero Nominal
        "<CharCode>EUR</CharCode><Nominal>0</Nominal><Name>Euro</Name><Value>20.0000</Value>",
        # Non-integer Nominal
        "<CharCode>EUR</CharCode><Nominal>1.5</Nominal><Name>Euro</Name><Value>20.0000</Value>",
        # Negative Value
        "<CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>-20.0000</Value>",
        # Zero Value
        "<CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>0.0000</Value>",
        # Non-numeric Value
        "<CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>invalid</Value>",
    ],
)
def test_parse_bnm_xml_invalid_fields_raises_invalid_response(valute_snippet):
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
        <Valute ID="1">
            {valute_snippet}
        </Valute>
    </ValCurs>"""
    with pytest.raises(InvalidResponse):
        parse_bnm_xml(xml)
