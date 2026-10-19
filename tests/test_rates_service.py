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


# User Story 2: Date fallback tests (T017)


def test_rates_service_fallback_to_prior_day():
    req_date = date(2026, 10, 19)
    prior_date = date(2026, 10, 18)
    xml_prior = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="18.10.2026" name="Official exchange rate">
        <Valute ID="47">
            <CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.5000</Value>
        </Valute>
    </ValCurs>"""

    # req_date has 404 (DateUnavailableError), prior_date has valid rates
    fake_client = FakeBnmClient({
        req_date: DateUnavailableError("No rates"),
        prior_date: xml_prior,
    })
    service = RatesService(client=fake_client)

    result = service.get_rates(req_date)
    assert result.date == prior_date
    assert result.source == "bnm"
    assert result.provenance_label == "BNM, official rate for 18.10.2026"
    assert result.notice is not None
    assert "18.10.2026" in result.notice
    assert fake_client.requested_dates == [req_date, prior_date]


def test_rates_service_fallback_on_empty_xml_response():
    req_date = date(2026, 10, 19)
    prior_date = date(2026, 10, 18)
    empty_xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate"></ValCurs>"""
    valid_xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="18.10.2026" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.5000</Value></Valute>
    </ValCurs>"""

    fake_client = FakeBnmClient({
        req_date: empty_xml,
        prior_date: valid_xml,
    })
    service = RatesService(client=fake_client)

    result = service.get_rates(req_date)
    assert result.date == prior_date
    assert result.notice is not None
    assert "18.10.2026" in result.notice


def test_rates_service_fallback_exactly_ten_days_boundary():
    from datetime import timedelta

    start_date = date(2026, 10, 20)
    # 10 days earlier is 2026-10-10
    day_10_earlier = start_date - timedelta(days=10)
    xml_day10 = f"""<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="{day_10_earlier.strftime('%d.%m.%Y')}" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.5000</Value></Valute>
    </ValCurs>"""

    responses = {}
    for i in range(10):
        d = start_date - timedelta(days=i)
        responses[d] = DateUnavailableError("404")
    responses[day_10_earlier] = xml_day10

    fake_client = FakeBnmClient(responses)
    service = RatesService(client=fake_client)

    result = service.get_rates(start_date)
    assert result.date == day_10_earlier
    assert len(fake_client.requested_dates) == 11


def test_rates_service_fallback_exhaustion_does_not_check_day_eleven():
    from datetime import timedelta

    start_date = date(2026, 10, 20)
    # Day 11 earlier has rates, but service must not check beyond 10 days earlier
    day_11_earlier = start_date - timedelta(days=11)
    xml_day11 = f"""<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="{day_11_earlier.strftime('%d.%m.%Y')}" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.5000</Value></Valute>
    </ValCurs>"""

    responses = {day_11_earlier: xml_day11}
    for i in range(11):  # days 0 to 10
        d = start_date - timedelta(days=i)
        responses[d] = DateUnavailableError("404")

    fake_client = FakeBnmClient(responses)
    service = RatesService(client=fake_client)

    with pytest.raises(NoRatesFoundError, match="[Nn]o rates"):
        service.get_rates(start_date)

    # Must only have checked days 0 through 10 (11 dates total)
    assert len(fake_client.requested_dates) == 11
    assert day_11_earlier not in fake_client.requested_dates


def test_rates_service_stops_on_malformed_xml_during_fallback():
    from datetime import timedelta

    start_date = date(2026, 10, 20)
    day_1_earlier = start_date - timedelta(days=1)
    day_2_earlier = start_date - timedelta(days=2)

    responses = {
        start_date: DateUnavailableError("404"),
        day_1_earlier: "<bad>corrupted xml",
        day_2_earlier: """<ValCurs Date="18.10.2026"><Valute><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.5000</Value></Valute></ValCurs>""",
    }
    fake_client = FakeBnmClient(responses)
    service = RatesService(client=fake_client)

    with pytest.raises(InvalidDataError):
        service.get_rates(start_date)

    # Must stop immediately on malformed data, not check day_2_earlier
    assert fake_client.requested_dates == [start_date, day_1_earlier]


def test_rates_service_stops_on_source_unavailable_during_fallback():
    from datetime import timedelta

    start_date = date(2026, 10, 20)
    day_1_earlier = start_date - timedelta(days=1)

    responses = {
        start_date: DateUnavailableError("404"),
        day_1_earlier: SourceUnavailableError("Network died"),
    }
    fake_client = FakeBnmClient(responses)
    service = RatesService(client=fake_client)

    with pytest.raises(SourceUnavailableError):
        service.get_rates(start_date)

    assert fake_client.requested_dates == [start_date, day_1_earlier]
