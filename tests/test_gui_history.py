"""Tests for the History tab and CSV export buttons (no pop-up windows)."""

from datetime import date
from decimal import Decimal
import tkinter as tk

import pytest

from converter.gui import ConverterApp
from converter.history import ConversionHistory
from converter.parser import Currency, RateSet
from converter.rates_service import RatesResult


RATES = RateSet(
    date=date(2026, 10, 19),
    currencies={
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.4523")),
        "USD": Currency(code="USD", name="US Dollar", nominal=1, value_mdl=Decimal("17.8541")),
    },
)


@pytest.fixture
def app(tk_session_root, tmp_path):
    win = tk.Toplevel(tk_session_root)
    application = ConverterApp(win, rates_service=None,
                               history=ConversionHistory(tmp_path / "history.json"),
                               export_dir=tmp_path / "export")
    application._on_rates_loaded(RatesResult(rates=RATES, date=RATES.date, source="bnm"))
    yield application
    win.destroy()


def do_convert(app, amount, src="EUR", dst="MDL"):
    app.amount_var.set(amount)
    app.from_currency_var.set(src)
    app.to_currency_var.set(dst)
    app._on_convert_clicked()


def history_texts(app):
    return [app.history_tree.item(i, "values")[1] for i in app.history_tree.get_children()]


def test_history_tab_starts_empty_with_disabled_buttons(app):
    assert app.history_tree.get_children() == ()
    assert app.notebook.tab(app.history_tab, "text") == "History"
    assert "No conversions yet" in app.history_caption_var.get()
    for button in (app.history_repeat_button, app.history_delete_button,
                   app.history_clear_button, app.history_export_button):
        assert "disabled" in button.state()


def test_each_conversion_is_added_to_history(app):
    do_convert(app, "100")
    do_convert(app, "10", "USD", "EUR")
    assert history_texts(app) == ["10 USD = 9.18 EUR", "100 EUR = 1945.23 MDL"]
    assert app.notebook.tab(app.history_tab, "text") == "History (2)"
    assert app.history_count_badge.cget("text") == "2"
    assert "disabled" not in app.history_clear_button.state()


def test_invalid_input_is_not_added(app):
    do_convert(app, "abc")
    assert app.history_tree.get_children() == ()


def test_history_survives_restart(app, tk_session_root, tmp_path):
    do_convert(app, "100")
    win = tk.Toplevel(tk_session_root)
    try:
        again = ConverterApp(win, history=ConversionHistory(tmp_path / "history.json"))
        assert history_texts(again) == ["100 EUR = 1945.23 MDL"]
    finally:
        win.destroy()


def test_search_filters_rows(app):
    do_convert(app, "100")
    do_convert(app, "10", "USD", "EUR")
    app.history_search_var.set("usd")
    assert history_texts(app) == ["10 USD = 9.18 EUR"]
    assert app.history_caption_var.get() == "Found 1 of 2."


def test_repeat_fills_form_and_converts(app):
    do_convert(app, "10", "USD", "EUR")
    app.amount_var.set("1")
    app.from_currency_var.set("EUR")
    app.notebook.select(2)
    first = app.history_tree.get_children()[0]
    app.history_tree.selection_set(first)
    app.root.update()
    assert "disabled" not in app.history_repeat_button.state()
    app.repeat_selected()
    assert app.notebook.index(app.notebook.select()) == 0
    assert (app.amount_var.get(), app.from_currency_var.get(),
            app.to_currency_var.get()) == ("10", "USD", "EUR")
    assert app.result_main_var.get() == "10 USD = 9.18 EUR"
    assert len(app.history) == 2


def test_repeat_needs_exactly_one_row(app):
    do_convert(app, "1")
    do_convert(app, "2")
    app.history_tree.selection_set(app.history_tree.get_children())
    app.root.update()
    assert "disabled" in app.history_repeat_button.state()
    app.repeat_selected()
    assert len(app.history) == 2


def test_delete_selected_rows(app):
    for amount in ("1", "2", "3"):
        do_convert(app, amount)
    rows = app.history_tree.get_children()
    app.history_tree.selection_set(rows[0], rows[2])
    app.delete_selected()
    assert history_texts(app) == ["2 EUR = 38.90 MDL"]
    assert "Deleted 2 rows" in app.banner_label.cget("text")


def test_clear_all_asks_in_banner_first(app):
    do_convert(app, "1")
    do_convert(app, "2")
    app.ask_clear_history()
    # Nothing is deleted until the user presses the button in the banner.
    assert len(app.history) == 2
    assert app.banner.winfo_manager() == "pack"
    assert app.banner_action.cget("text") == "Clear"
    app.banner_action.invoke()
    assert len(app.history) == 0
    assert app.history_tree.get_children() == ()
    assert "History cleared" in app.banner_label.cget("text")


def test_export_history_csv_writes_filtered_rows(app, tmp_path):
    do_convert(app, "100")
    do_convert(app, "10", "USD", "EUR")
    app.history_search_var.set("usd")
    app.export_history_csv()
    files = list((tmp_path / "export").glob("history_*.csv"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 2 and "USD" in lines[1]
    assert "Saved 1 rows" in app.banner_label.cget("text")


def test_export_empty_history_warns(app, tmp_path):
    app.export_history_csv()
    assert "Nothing to export" in app.banner_label.cget("text")
    assert not (tmp_path / "export").exists()


def test_export_rates_csv(app, tmp_path):
    app.export_rates_csv()
    files = list((tmp_path / "export").glob("bnm_rates_20261019_*.csv"))
    assert len(files) == 1
    assert "Saved 3 rows" in app.banner_label.cget("text")


def test_export_rates_without_rates_warns(tk_session_root, tmp_path):
    win = tk.Toplevel(tk_session_root)
    try:
        application = ConverterApp(win, export_dir=tmp_path)
        application.export_rates_csv()
        assert "rates are not loaded" in application.banner_label.cget("text")
    finally:
        win.destroy()


def test_damaged_history_file_is_reported_in_banner(tk_session_root, tmp_path):
    path = tmp_path / "history.json"
    path.write_text("broken", encoding="utf-8")
    win = tk.Toplevel(tk_session_root)
    try:
        application = ConverterApp(win, history=ConversionHistory(path))
        assert "damaged" in application.banner_label.cget("text")
    finally:
        win.destroy()


class OfflineService:
    def __init__(self, cached):
        self.cache = type("C", (), {"load": lambda _self: cached})()

    def get_rates(self, target_date):
        from converter.bnm_client import SourceUnavailableError
        raise SourceUnavailableError("network unreachable")


def _wait(win, cond):
    import time
    for _ in range(50):
        win.update()
        if cond():
            return
        time.sleep(0.02)


def test_startup_without_network_fills_currencies_from_cache(tk_session_root):
    cached = RateSet(date=date(2026, 10, 15), currencies=RATES.currencies, source="cache",
                     is_cached=True)
    win = tk.Toplevel(tk_session_root)
    try:
        application = ConverterApp(win, rates_service=OfflineService(cached))
        _wait(win, lambda: application.current_rates_result is not None)
        assert application.current_rates_result.is_cached
        assert "USD" in application.from_combo["values"]
        assert "saved rates of 15.10.2026" in application.banner_label.cget("text")
        assert application.header_stats_var.get().startswith("Rates: cache from 15.10.2026")
    finally:
        win.destroy()


def test_startup_without_network_and_cache_warns(tk_session_root):
    win = tk.Toplevel(tk_session_root)
    try:
        application = ConverterApp(win, rates_service=OfflineService(None))
        _wait(win, lambda: application.banner.winfo_manager() == "pack")
        assert "BNM is unavailable" in application.banner_label.cget("text")
        assert application.banner_action.cget("text") == "Retry"
    finally:
        win.destroy()


def test_default_pair_is_eur_to_mdl_after_rates_load(app):
    assert (app.from_currency_var.get(), app.to_currency_var.get()) == ("EUR", "MDL")
