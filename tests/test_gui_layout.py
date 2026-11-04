"""Tests for the redesigned window: tabs, banners, rates table, keyboard."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import time
import tkinter as tk

import pytest

from converter.gui import ConverterApp
from converter.parser import Currency, RateSet
from converter.rates_service import RatesResult


RATES = RateSet(
    date=date(2026, 10, 19),
    currencies={
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.4523")),
        "USD": Currency(code="USD", name="US Dollar", nominal=1, value_mdl=Decimal("17.8541")),
        "HUF": Currency(code="HUF", name="Hungarian Forint", nominal=100,
                        value_mdl=Decimal("4.8765")),
    },
)


class FakeService:
    def __init__(self):
        self.calls = 0

    def get_rates(self, target_date):
        self.calls += 1
        return RatesResult(rates=RATES, date=RATES.date, source="bnm")


@pytest.fixture
def app(tk_session_root):
    win = tk.Toplevel(tk_session_root)
    application = ConverterApp(win, rates_service=None)
    yield application
    win.destroy()


def pump(app, rounds=20):
    for _ in range(rounds):
        app.root.update()


def load(app):
    app._on_rates_loaded(RatesResult(rates=RATES, date=RATES.date, source="bnm"))


def test_window_has_converter_and_rates_tabs(app):
    tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
    assert tabs == ["Converter", "Rates"]


def test_gui_does_not_use_message_boxes():
    source = (Path(__file__).parents[1] / "src" / "converter" / "gui.py").read_text(
        encoding="utf-8")
    assert "messagebox" not in source
    assert "Toplevel" not in source


def test_empty_state_is_shown_until_there_is_a_result(app):
    pump(app)
    assert app.empty_state.winfo_manager() == "pack"
    assert app.result_view.winfo_manager() == ""
    load(app)
    app.amount_var.set("100")
    app.from_currency_var.set("EUR")
    app.to_currency_var.set("MDL")
    app._on_convert_clicked()
    pump(app)
    assert app.result_main_var.get() == "100 EUR = 1945.23 MDL"
    assert app.result_view.winfo_manager() == "pack"
    assert app.empty_state.winfo_manager() == ""
    assert app.result_route_badge.cget("text") == "EUR → MDL"


def test_escape_clears_result(app):
    load(app)
    app.amount_var.set("1")
    app.from_currency_var.set("EUR")
    app.to_currency_var.set("MDL")
    app._on_convert_clicked()
    app._clear_form_result()
    assert app.result_main_var.get() == ""
    assert app.empty_state.winfo_manager() == "pack"


def test_notice_strip_is_hidden_when_empty(app):
    load(app)
    app.amount_var.set("1")
    app.from_currency_var.set("EUR")
    app.to_currency_var.set("MDL")
    app._on_convert_clicked()
    assert app.result_notice_lbl.winfo_manager() == ""
    app.result_notice_var.set("No rates published for 25.10.2026")
    assert app.result_notice_lbl.winfo_manager() == "pack"


def test_cache_provenance_uses_warning_colours(app):
    app.result_main_var.set("1 EUR = 19.45 MDL")
    app.result_provenance_var.set("cache from 15.10.2026")
    assert app.result_provenance_lbl.cget("bg").upper() == "#FFF4E5"
    app.result_provenance_var.set("BNM, official rate for 19.10.2026")
    assert app.result_provenance_lbl.cget("bg").upper() == "#EBFBEE"


def test_error_line_takes_no_space_when_empty(app):
    pump(app)
    assert app.validation_label.winfo_manager() == ""
    app.amount_var.set("abc")
    app.from_currency_var.set("EUR")
    app.to_currency_var.set("MDL")
    app._on_convert_clicked()
    assert app.validation_error_var.get() != ""
    assert app.validation_label.winfo_manager() == "grid"


def test_rates_table_is_filled_and_searchable(app):
    assert app.rates_tree.get_children() == ()
    load(app)
    rows = app.rates_tree.get_children()
    assert list(rows)[:2] == ["EUR", "USD"]
    assert len(rows) == 4
    assert app.rates_tree.item("HUF", "values")[3:] == ("4.8765", "0.0488")
    app.rates_search_var.set("dollar")
    assert app.rates_tree.get_children() == ("USD",)
    assert app.rates_count_badge.cget("text") == "1"


def test_double_click_on_rate_opens_converter(app):
    load(app)
    app.notebook.select(1)
    app.rates_tree.selection_set("USD")
    app._on_rate_row_activated()
    assert app.from_currency_var.get() == "USD"
    assert app.to_currency_var.get() == "MDL"
    assert app.notebook.index(app.notebook.select()) == 0


def test_header_shows_loaded_rates(app):
    load(app)
    assert app.header_stats_var.get() == (
        "Rates: BNM, official rate for 19.10.2026  ·  4 currencies")


def test_currency_names_under_selectors(app):
    load(app)
    app.from_currency_var.set("HUF")
    app.to_currency_var.set("MDL")
    assert app.from_name_label.cget("text") == "Hungarian Forint"
    assert app.to_name_label.cget("text") == "Moldovan Leu"


def test_notify_banner_kinds_and_close(app):
    app.notify("Saved", "ok")
    assert app.banner.winfo_manager() == "pack"
    assert app.banner_label.cget("bg").upper() == "#EBFBEE"
    app.notify("Rates not loaded", "error", action=lambda: None, action_text="Retry")
    assert app.banner_label.cget("bg").upper() == "#FFF0F0"
    assert app.banner_action.cget("text") == "Retry"
    app.hide_banner()
    assert app.banner.winfo_manager() == ""


def test_cache_offer_is_a_strip_under_the_header(app):
    app.show_cache_offer("Saved rates from 15.10.2026 are available.", lambda: None)
    assert app.cache_prompt_frame.winfo_manager() == "pack"
    assert app.cache_prompt_frame.master is app.root
    app.hide_cache_offer()
    assert app.cache_prompt_frame.winfo_manager() == ""


def test_enter_key_converts(app):
    load(app)
    app.amount_var.set("10")
    app.from_currency_var.set("USD")
    app.to_currency_var.set("MDL")
    app._on_enter_pressed()
    assert app.result_main_var.get() == "10 USD = 178.54 MDL"


def test_enter_does_nothing_while_form_incomplete(app):
    load(app)
    app.amount_var.set("")
    app._on_enter_pressed()
    assert app.validation_error_var.get() == ""


def test_previous_day_button_shifts_date(app):
    app.date_var.set("01.11.2026")
    app._shift_date(-1)
    assert app.date_var.get() == "31.10.2026"
    app.date_var.set("garbage")
    app._shift_date(-1)
    assert app.date_var.get() != "garbage"


def test_copy_result_to_clipboard(app):
    app.result_main_var.set("100 EUR = 1945.23 MDL")
    app.result_reverse_var.set("1 MDL = 0.0514 EUR")
    app._copy_result()
    assert app.root.clipboard_get().startswith("100 EUR = 1945.23 MDL")


def test_load_rates_tab_uses_service(tk_session_root):
    win = tk.Toplevel(tk_session_root)
    try:
        service = FakeService()
        application = ConverterApp(win, rates_service=service)
        application.date_var.set("19.10.2026")
        application._on_load_rates_clicked()
        for _ in range(40):
            win.update()
            if application.rates_tree.get_children():
                break
            time.sleep(0.02)
        assert "EUR" in application.rates_tree.get_children()
        assert service.calls >= 1
    finally:
        win.destroy()


def test_convert_button_is_disabled_while_busy(app):
    app.amount_var.set("1")
    app.from_currency_var.set("EUR")
    app.to_currency_var.set("MDL")
    app._set_busy(True)
    assert "disabled" in app.convert_button.state()
    assert app.convert_button.cget("text") == "Converting..."
    app._set_busy(False)
    assert "disabled" not in app.convert_button.state()
