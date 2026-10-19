"""Additional edge-case tests against spec.md acceptance scenarios."""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from converter.bnm_client import DateUnavailableError
from converter.cache import RateCache
from converter.converter import convert
from converter.parser import parse_bnm_xml
from converter.rates_service import RatesService
from converter.validation import ValidationError, parse_amount

FIXTURE = Path(__file__).parent / "fixtures" / "bnm_rates.xml"
CORE_MODULES = ["bnm_client", "parser", "cache", "rates_service", "converter", "validation"]


@pytest.fixture
def fixture_rates():
    return parse_bnm_xml(FIXTURE.read_text(encoding="utf-8"))


class OneDayClient:
    """Fake BNM client that knows rates for a single date only."""

    def __init__(self, known_date, xml):
        self.known_date = known_date
        self.xml = xml

    def fetch_rates(self, target_date):
        if target_date != self.known_date:
            raise DateUnavailableError(str(target_date))
        return self.xml


def test_cross_conversion_between_two_nominal_currencies(fixture_rates):
    # ALL is quoted per 10 units, HUF per 100 units
    forward = convert(Decimal("1000"), "ALL", "HUF", fixture_rates)
    expected = Decimal("1000") * (Decimal("2.2010") / 10) / (Decimal("4.8765") / 100)
    assert forward.result == expected.quantize(Decimal("0.01"))

    back = convert(forward.result, "HUF", "ALL", fixture_rates)
    assert abs(back.result - Decimal("1000")) <= Decimal("0.01")


def test_reverse_rate_is_inverse_of_forward_rate(fixture_rates):
    eur_mdl = convert(Decimal("1"), "EUR", "MDL", fixture_rates)
    mdl_eur = convert(Decimal("1"), "MDL", "EUR", fixture_rates)
    assert eur_mdl.reverse_rate * mdl_eur.reverse_rate == pytest.approx(Decimal("1"))


@pytest.mark.parametrize("text, expected", [
    ("100,5", Decimal("100.5")),
    ("0,01", Decimal("0.01")),
    ("1000000", Decimal("1000000")),
])
def test_parse_amount_accepts_small_and_large_values(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["1e3", "inf", "nan", "--5"])
def test_parse_amount_rejects_special_numeric_forms(text):
    with pytest.raises(ValidationError):
        parse_amount(text)


def test_rates_service_uses_rate_published_ten_days_earlier():
    target = date(2026, 10, 25)
    published = date(2026, 10, 15)
    xml = FIXTURE.read_text(encoding="utf-8").replace("19.10.2026", "15.10.2026")
    result = RatesService(client=OneDayClient(published, xml)).get_rates(target)
    assert result.date == published
    assert "15.10.2026" in result.notice


def test_cache_survives_restart_with_new_instances(tmp_path, fixture_rates):
    cache_file = tmp_path / "rates.json"
    RateCache(cache_file).save(fixture_rates)

    restarted = RatesService(client=OneDayClient(None, ""), cache=RateCache(cache_file))
    cached = restarted.get_cached_rates()
    assert cached is not None
    assert cached.is_cached is True
    assert cached.provenance_label == f"cache from {fixture_rates.date.strftime('%d.%m.%Y')}"
    assert cached.rates.currencies["HUF"].nominal == 100


def test_corrupted_cache_file_is_ignored_without_crash(tmp_path):
    cache_file = tmp_path / "rates.json"
    cache_file.write_text("{not json", encoding="utf-8")
    service = RatesService(client=OneDayClient(None, ""), cache=RateCache(cache_file))
    assert service.get_cached_rates() is None


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_modules_do_not_import_gui(module):
    source = Path(__file__).parents[1] / "src" / "converter" / f"{module}.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "tkinter" not in imported
    assert "converter.gui" not in imported
