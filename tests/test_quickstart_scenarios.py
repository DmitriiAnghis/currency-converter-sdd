"""Automated validation of all Quickstart scenarios (T027)."""

from datetime import date, timedelta
from decimal import Decimal
import time
import tkinter as tk
import pytest

from converter.bnm_client import DateUnavailableError, SourceUnavailableError
from converter.cache import RateCache
from converter.converter import convert
from converter.gui import ConverterApp
from converter.parser import Currency, RateSet
from converter.rates_service import RatesService
from converter.validation import ValidationError, parse_amount


class DeterministicBnmClient:
    """Deterministic fake client for scenarios."""

    def __init__(self, responses=None):
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


def test_quickstart_scenario_1_and_2_and_3(tmp_path, tk_session_root):
    # Scenario 1, 2, 3: Conversion, cross rates, same-currency, and provenance
    target_date = date(2026, 10, 19)
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.4523</Value></Valute>
        <Valute ID="44"><CharCode>USD</CharCode><Nominal>1</Nominal><Name>US Dollar</Name><Value>17.8541</Value></Valute>
        <Valute ID="1"><CharCode>ALL</CharCode><Nominal>10</Nominal><Name>Albanian Lek</Name><Value>2.2010</Value></Valute>
    </ValCurs>"""

    cache = RateCache(cache_file=tmp_path / "cache.json")
    client = DeterministicBnmClient({target_date: xml})
    service = RatesService(client=client, cache=cache)

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service)

        # 1. 100 EUR to MDL
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")
        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if app.result_main_var.get():
                break
            time.sleep(0.05)

        assert app.result_main_var.get() == "100 EUR = 1945.23 MDL"
        assert app.result_reverse_var.get() == "1 MDL = 0.0514 EUR"
        assert app.result_provenance_var.get() == "BNM, official rate for 19.10.2026"

        # 2. EUR to USD
        app.to_currency_var.set("USD")
        app._on_convert_clicked()
        for _ in range(20):
            win.update()
            if "USD" in app.result_main_var.get():
                break
            time.sleep(0.05)

        # 100 * 19.4523 / 17.8541 = 108.95
        assert app.result_main_var.get() == "100 EUR = 108.95 USD"
        assert app.result_reverse_var.get() == "1 USD = 0.9178 EUR"

        # USD to EUR
        app.from_currency_var.set("USD")
        app.to_currency_var.set("EUR")
        app._on_convert_clicked()
        for _ in range(20):
            win.update()
            if "100 USD" in app.result_main_var.get():
                break
            time.sleep(0.05)

        # 100 * 17.8541 / 19.4523 = 91.78
        assert app.result_main_var.get() == "100 USD = 91.78 EUR"
        assert app.result_reverse_var.get() == "1 EUR = 1.0895 USD"

        # 3. Same currency
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("EUR")
        app._on_convert_clicked()
        for _ in range(20):
            win.update()
            if "100 EUR = 100.00 EUR" in app.result_main_var.get():
                break
            time.sleep(0.05)

        assert app.result_main_var.get() == "100 EUR = 100.00 EUR"
        assert app.result_reverse_var.get() == "1 EUR = 1 EUR" or "1 EUR = 1" in app.result_reverse_var.get()
    finally:
        win.destroy()


def test_quickstart_scenario_4_comma_and_period_and_invalid_amounts():
    # Comma and period
    assert parse_amount("100,50") == Decimal("100.50")
    assert parse_amount("100.50") == Decimal("100.50")

    # Invalid inputs
    for bad in ["", "   ", "0", "-10", "abc", "1,2.3", "1.2.3"]:
        with pytest.raises(ValidationError):
            parse_amount(bad)


def test_quickstart_scenario_5_fallback_date(tmp_path, tk_session_root):
    # Selected date has no rates; first prior available date in 10-day lookback is used
    req_date = date(2026, 10, 25)
    effective_date = date(2026, 10, 23)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="23.10.2026" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.6000</Value></Valute>
    </ValCurs>"""

    cache = RateCache(cache_file=tmp_path / "cache.json")
    client = DeterministicBnmClient({effective_date: xml})
    service = RatesService(client=client, cache=cache)

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service)
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("25.10.2026")

        app._on_convert_clicked()
        for _ in range(20):
            win.update()
            if app.result_provenance_var.get():
                break
            time.sleep(0.05)

        assert "23.10.2026" in app.result_provenance_var.get()
        assert "BNM, official rate for 23.10.2026" == app.result_provenance_var.get()
        assert "25.10.2026" in app.result_notice_var.get()
        assert "23.10.2026" in app.result_notice_var.get()
        assert app.result_main_var.get() == "100 EUR = 1960.00 MDL"
    finally:
        win.destroy()


def test_quickstart_scenarios_6_and_7_offline_cache_and_restart(tmp_path, tk_session_root):
    # Scenario 6: Online fetch caches rates; then offline network prompts user for cache
    cache_path = tmp_path / "app_cache.json"
    cache = RateCache(cache_file=cache_path)

    # Online fetch
    req_date = date(2026, 10, 19)
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <ValCurs Date="19.10.2026" name="Official exchange rate">
        <Valute ID="47"><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Euro</Name><Value>19.4523</Value></Valute>
    </ValCurs>"""
    client_online = DeterministicBnmClient({req_date: xml})
    service_online = RatesService(client=client_online, cache=cache)
    service_online.get_rates(req_date)

    assert cache_path.exists()

    # Now offline request
    client_offline = DeterministicBnmClient({req_date: SourceUnavailableError("No connection")})
    service_offline = RatesService(client=client_offline, cache=cache)

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service_offline)
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()
        for _ in range(20):
            win.update()
            if "19.10.2026" in app.cache_prompt_label.cget("text"):
                break
            time.sleep(0.05)

        # Confirm dated cache-use offer
        assert "19.10.2026" in app.cache_prompt_label.cget("text")
        assert app.result_main_var.get() == ""

        # Accept cache
        app._on_accept_cache()
        win.update()

        assert app.result_main_var.get() == "100 EUR = 1945.23 MDL"
        assert app.result_provenance_var.get() == "cache from 19.10.2026"
    finally:
        win.destroy()

    # Scenario 7: App restart while offline preserves cache
    cache_reloaded = RateCache(cache_file=cache_path)
    loaded_rates = cache_reloaded.load()
    assert loaded_rates is not None
    assert loaded_rates.date == date(2026, 10, 19)
    assert loaded_rates.source == "cache"
    assert loaded_rates.is_cached is True
    assert "EUR" in loaded_rates.currencies
