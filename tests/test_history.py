"""Tests for the conversion history (JSON file, search, delete, CSV export)."""

from datetime import date, datetime
from decimal import Decimal
import csv
import json

from converter.converter import Conversion, convert
from converter.history import (
    ConversionHistory,
    HistoryEntry,
    export_rates_csv,
    get_default_history_path,
)
from converter.parser import Currency, RateSet


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
NOW = datetime(2026, 11, 7, 14, 30)


def conv(amount="100", src="EUR", dst="MDL", rates=RATES) -> Conversion:
    return convert(Decimal(amount), src, dst, rates)


def test_add_puts_newest_first_with_formatted_fields():
    h = ConversionHistory()
    h.add(conv("100"), NOW)
    second = h.add(conv("10", "USD", "EUR"), NOW)
    assert [e.id for e in h.entries] == [2, 1]
    assert second.time == "07.11.2026 14:30"
    assert h.entries[1].text == "100 EUR = 1945.23 MDL"
    assert h.entries[1].rate_date == "19.10.2026"
    assert h.entries[1].source == "BNM"


def test_cache_source_is_marked():
    cached = RateSet(date=RATES.date, currencies=RATES.currencies, source="cache",
                     is_cached=True)
    h = ConversionHistory()
    assert h.add(conv(rates=cached), NOW).source == "cache"


def test_history_is_saved_and_loaded_from_file(tmp_path):
    path = tmp_path / "sub" / "history.json"
    h = ConversionHistory(path)
    h.add(conv("100"), NOW)
    h.add(conv("5", "USD", "MDL"), NOW)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    again = ConversionHistory(path)
    assert [e.text for e in again.entries] == [e.text for e in h.entries]
    assert again.load_error is None


def test_damaged_file_gives_empty_history_and_message(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{not json", encoding="utf-8")
    h = ConversionHistory(path)
    assert len(h) == 0
    assert "damaged" in h.load_error
    h.add(conv(), NOW)  # and the file is usable again
    assert len(ConversionHistory(path)) == 1


def test_wrong_schema_version_is_reset(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"schema_version": 99, "entries": []}), encoding="utf-8")
    assert ConversionHistory(path).load_error is not None


def test_ids_keep_growing_after_delete():
    h = ConversionHistory()
    for _ in range(3):
        h.add(conv(), NOW)
    h.delete([3])
    assert h.add(conv(), NOW).id == 3  # max id is 2 now
    h.delete([1, 2])
    assert [e.id for e in h.entries] == [3]


def test_delete_returns_count_and_ignores_unknown_ids(tmp_path):
    h = ConversionHistory(tmp_path / "h.json")
    h.add(conv(), NOW)
    h.add(conv(), NOW)
    assert h.delete([1, 42]) == 1
    assert h.delete([]) == 0
    assert len(ConversionHistory(tmp_path / "h.json")) == 1


def test_clear_removes_everything(tmp_path):
    h = ConversionHistory(tmp_path / "h.json")
    h.add(conv(), NOW)
    h.add(conv(), NOW)
    assert h.clear() == 2
    assert len(h) == 0
    assert len(ConversionHistory(tmp_path / "h.json")) == 0


def test_max_entries_limit_drops_oldest():
    h = ConversionHistory(max_entries=3)
    for amount in ("1", "2", "3", "4"):
        h.add(conv(amount), NOW)
    assert [e.amount for e in h.entries] == ["4", "3", "2"]


def test_search_by_code_amount_and_date():
    h = ConversionHistory()
    h.add(conv("100", "EUR", "MDL"), NOW)
    h.add(conv("7", "USD", "HUF"), NOW)
    assert [e.amount for e in h.search("usd")] == ["7"]
    assert [e.amount for e in h.search("eur mdl")] == ["100"]
    assert len(h.search("19.10.2026")) == 2
    assert len(h.search("  ")) == 2
    assert h.search("gbp") == []


def test_get_returns_entry_or_none():
    h = ConversionHistory()
    entry = h.add(conv(), NOW)
    assert h.get(entry.id) == entry
    assert h.get(999) is None


def test_export_csv_opens_in_excel(tmp_path):
    h = ConversionHistory()
    h.add(conv("100"), NOW)
    h.add(conv("12.5", "USD", "EUR"), NOW)
    path = tmp_path / "out" / "history.csv"
    assert ConversionHistory.export_csv(h.entries, path) == 2
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM: Excel reads UTF-8 correctly
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[0] == ["Time", "Amount", "From", "Result", "To", "Rate date", "Source"]
    assert rows[2] == ["07.11.2026 14:30", "100", "EUR", "1945.23", "MDL", "19.10.2026", "BNM"]


def test_export_rates_csv_puts_popular_first(tmp_path):
    path = tmp_path / "rates.csv"
    assert export_rates_csv(RATES, path) == 4
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert [r[0] for r in rows[1:]] == ["EUR", "USD", "HUF", "MDL"]
    assert rows[3] == ["HUF", "Hungarian Forint", "100", "4.8765", "0.0488", "19.10.2026"]


def test_default_history_path_is_next_to_cache():
    path = get_default_history_path()
    assert path.name == "history.json"
    assert path.parent.name == "BnmCurrencyConverter"


def test_entry_matches_is_case_insensitive():
    e = HistoryEntry(1, "07.11.2026 14:30", "100", "EUR", "MDL", "1945.23", "19.10.2026", "BNM")
    assert e.matches("Eur")
    assert e.matches("1945")
    assert not e.matches("usd")
