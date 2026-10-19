"""Tests for GUI display, currency ordering, and interaction."""

from datetime import date
from decimal import Decimal
import time
import tkinter as tk
import pytest

from converter.gui import ConverterApp, order_currencies
from converter.parser import Currency, RateSet
from converter.rates_service import InvalidDataError, RatesResult


def test_order_currencies():
    codes = ["CAD", "MDL", "USD", "ALL", "EUR", "RON", "RUB", "UAH", "GBP", "CHF"]
    ordered = order_currencies(codes)

    # Popular currencies must appear first in specified order
    assert ordered[:6] == ["EUR", "USD", "RON", "UAH", "RUB", "GBP"]
    # Remaining currencies appear alphabetically
    assert ordered[6:] == ["ALL", "CAD", "CHF", "MDL"]


class ImmediateFakeRatesService:
    def __init__(self, rate_set=None, error=None):
        self.rate_set = rate_set
        self.error = error

    def get_rates(self, target_date: date) -> RatesResult:
        if self.error:
            raise self.error
        return RatesResult(
            rates=self.rate_set,
            date=self.rate_set.date,
            source="bnm",
            is_cached=False,
        )


def test_gui_conversion_flow_and_display(tk_session_root):
    sample_rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.4523")),
    }
    rate_set = RateSet(date=date(2026, 10, 19), currencies=sample_rates)
    service = ImmediateFakeRatesService(rate_set=rate_set)

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service)
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        # Wait briefly for thread to finish and after callback to run
        for _ in range(20):
            win.update()
            if app.result_main_var.get():
                break
            time.sleep(0.05)

        assert "100 EUR = 1945.23 MDL" == app.result_main_var.get()
        assert "1 MDL = 0.0514 EUR" == app.result_reverse_var.get()
        assert "BNM, official rate for 19.10.2026" == app.result_provenance_var.get()
        assert app.validation_error_var.get() == ""
    finally:
        win.destroy()


def test_gui_shows_error_on_malformed_data(tk_session_root):
    service = ImmediateFakeRatesService(error=InvalidDataError("Malformed source XML"))

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service)
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if app.validation_error_var.get():
                break
            time.sleep(0.05)

        assert "Malformed source XML" in app.validation_error_var.get()
        assert app.result_main_var.get() == ""
    finally:
        win.destroy()


def test_gui_displays_fallback_notice_and_actual_date(tk_session_root):
    sample_rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.5000")),
    }
    rate_set = RateSet(date=date(2026, 10, 18), currencies=sample_rates)
    fallback_notice = "No rates published for 19.10.2026; using official rates from 18.10.2026."

    class FallbackFakeRatesService:
        def get_rates(self, target_date: date) -> RatesResult:
            return RatesResult(
                rates=rate_set,
                date=rate_set.date,
                source="bnm",
                is_cached=False,
                notice=fallback_notice,
            )

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=FallbackFakeRatesService())
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if app.result_notice_var.get():
                break
            time.sleep(0.05)

        assert "18.10.2026" in app.result_provenance_var.get()
        assert app.result_notice_var.get() == fallback_notice
        assert "100 EUR = 1950.00 MDL" == app.result_main_var.get()
    finally:
        win.destroy()


def test_gui_reports_lookback_exhaustion_without_conversion(tk_session_root):
    from converter.rates_service import NoRatesFoundError

    service = ImmediateFakeRatesService(
        error=NoRatesFoundError("No rates found for 19.10.2026 or the 10-day lookback period.")
    )

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=service)
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if app.validation_error_var.get():
                break
            time.sleep(0.05)

        assert "lookback period" in app.validation_error_var.get()
        assert app.result_main_var.get() == ""
    finally:
        win.destroy()


def test_gui_source_unavailable_offers_cache_and_accept(tk_session_root):
    from converter.bnm_client import SourceUnavailableError

    cached_rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.3000")),
    }
    cached_set = RateSet(date=date(2026, 10, 15), currencies=cached_rates, source="cache", is_cached=True)

    class OfflineFakeCache:
        def load(self):
            return cached_set

    class OfflineService:
        cache = OfflineFakeCache()

        def get_rates(self, target_date: date):
            raise SourceUnavailableError("Cannot connect to BNM server")

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=OfflineService())
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if "15.10.2026" in app.cache_prompt_label.cget("text"):
                break
            time.sleep(0.05)

        # Cache offer is shown
        assert "15.10.2026" in app.cache_prompt_label.cget("text")
        assert app.result_main_var.get() == ""

        # Accept cache
        app._on_accept_cache()
        win.update()

        assert "100 EUR = 1930.00 MDL" == app.result_main_var.get()
        assert "cache from 15.10.2026" == app.result_provenance_var.get()
    finally:
        win.destroy()


def test_gui_source_unavailable_declining_cache(tk_session_root):
    from converter.bnm_client import SourceUnavailableError

    cached_rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.3000")),
    }
    cached_set = RateSet(date=date(2026, 10, 15), currencies=cached_rates, source="cache", is_cached=True)

    class OfflineFakeCache:
        def load(self):
            return cached_set

    class OfflineService:
        cache = OfflineFakeCache()

        def get_rates(self, target_date: date):
            raise SourceUnavailableError("Cannot connect to BNM server")

    win = tk.Toplevel(tk_session_root)
    try:
        app = ConverterApp(win, rates_service=OfflineService())
        app.amount_var.set("100")
        app.from_currency_var.set("EUR")
        app.to_currency_var.set("MDL")
        app.date_var.set("19.10.2026")

        app._on_convert_clicked()

        for _ in range(20):
            win.update()
            if "15.10.2026" in app.cache_prompt_label.cget("text"):
                break
            time.sleep(0.05)

        # Decline cache
        app._on_decline_cache()
        win.update()

        assert "declined" in app.validation_error_var.get()
        assert app.result_main_var.get() == ""
    finally:
        win.destroy()
