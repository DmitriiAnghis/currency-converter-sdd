"""Tests for rates service (User Story 1: Single-date retrieval)."""

from datetime import date
from decimal import Decimal
import pytest

from converter.bnm_client import DateUnavailableError, SourceUnavailableError
from converter.parser import Currency, EmptyResponse, InvalidResponse, RateSet
from converter.rates_service import (
    InvalidDataError,
    NoRatesFoundError,
    RatesResult,
    RatesService,
)


class FakeBnmClient:
    def __init__(self, responses=None):
        # responses: dict mapping date to (status, body_or_exc)
        self.responses = responses or {}
        self.requested_dates = []

    def fetch_rates(self, target_date: date) -> str:
        self.requested_dates.append(target_date)
        if target_date not in self.responses:
            raise DateUnavailableError(f"No rates for {target_date}")
        res = self.responses[target_date]
        if isinstance(res, Exception):
            raise res
        return res


def test_rates_service_single_date_success():
    req_date = date(2026, 10, 19)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
        <Valute ID="47">
            <CharCode>EUR</CharCode>
            <Nominal>1</Nominal>
            <Name>Euro</Name>
            <Value>19.4523</Value>
        </Valute>
    </ValCurs>"""
    fake_client = FakeBnmClient({req_date: xml})
    service = RatesService(client=fake_client)

    result = service.get_rates(req_date)
    assert isinstance(result, RatesResult)
    assert result.date == req_date
    assert result.source == "bnm"
    assert result.is_cached is False
    assert result.notice is None
    assert result.provenance_label == "BNM, official rate for 19.10.2026"
    assert "EUR" in result.rates.currencies
    assert "MDL" in result.rates.currencies


def test_rates_service_empty_response_raises_no_rates():
    req_date = date(2026, 10, 19)
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
    </ValCurs>"""
    fake_client = FakeBnmClient({req_date: xml})
    service = RatesService(client=fake_client)

    with pytest.raises(NoRatesFoundError):
        service.get_rates(req_date)


def test_rates_service_malformed_xml_raises_invalid_data():
    req_date = date(2026, 10, 19)
    fake_client = FakeBnmClient({req_date: "<broken>xml"})
    service = RatesService(client=fake_client)

    with pytest.raises(InvalidDataError, match="malformed|invalid"):
        service.get_rates(req_date)


def test_rates_service_source_unavailable_surfaced():
    req_date = date(2026, 10, 19)
    fake_client = FakeBnmClient({req_date: SourceUnavailableError("Connection failed")})
    service = RatesService(client=fake_client)

    with pytest.raises(SourceUnavailableError):
        service.get_rates(req_date)
