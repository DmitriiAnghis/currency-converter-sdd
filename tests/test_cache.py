"""Tests for versioned JSON rate cache."""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import pytest

from converter.cache import (
    CacheWriteError,
    InvalidCacheError,
    RateCache,
    get_default_cache_path,
)
from converter.parser import Currency, RateSet


@pytest.fixture
def sample_rate_set() -> RateSet:
    rates = {
        "MDL": Currency(code="MDL", name="Moldovan Leu", nominal=1, value_mdl=Decimal("1")),
        "EUR": Currency(code="EUR", name="Euro", nominal=1, value_mdl=Decimal("19.4523")),
        "ALL": Currency(code="ALL", name="Albanian Lek", nominal=10, value_mdl=Decimal("2.2010")),
    }
    return RateSet(
        date=date(2026, 10, 19),
        currencies=rates,
        source="bnm",
        is_cached=False,
    )


def test_cache_missing_file_returns_none(tmp_path: Path):
    cache = RateCache(cache_file=tmp_path / "nonexistent.json")
    assert cache.load() is None


def test_cache_round_trip_and_decimal_precision(tmp_path: Path, sample_rate_set: RateSet):
    cache_file = tmp_path / "cache.json"
    cache = RateCache(cache_file=cache_file)

    cache.save(sample_rate_set)
    assert cache_file.exists()

    # Verify JSON content structure and string serialization of decimals
    raw_data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert raw_data["schema_version"] == 1
    assert raw_data["date"] == "2026-10-19"
    assert isinstance(raw_data["currencies"], list)

    eur_record = next(c for c in raw_data["currencies"] if c["code"] == "EUR")
    assert eur_record["value_mdl"] == "19.4523"
    assert eur_record["nominal"] == 1
    assert eur_record["name"] == "Euro"

    # Reload through cache
    loaded = cache.load()
    assert loaded is not None
    assert loaded.date == date(2026, 10, 19)
    assert loaded.source == "cache"
    assert loaded.is_cached is True
    assert loaded.currencies["EUR"].value_mdl == Decimal("19.4523")
    assert loaded.currencies["ALL"].nominal == 10
    assert loaded.currencies["ALL"].value_mdl == Decimal("2.2010")
    assert loaded.currencies["MDL"].value_mdl == Decimal("1")


def test_cache_unreadable_json_raises_invalid_cache(tmp_path: Path):
    cache_file = tmp_path / "corrupt.json"
    cache_file.write_text("{not valid json", encoding="utf-8")

    cache = RateCache(cache_file=cache_file)
    with pytest.raises(InvalidCacheError, match="[Uu]nreadable|[Cc]orrupted"):
        cache.load()


@pytest.mark.parametrize(
    "bad_content",
    [
        {"date": "2026-10-19", "currencies": []},  # Missing schema_version
        {"schema_version": 999, "date": "2026-10-19", "currencies": []},  # Unsupported schema_version
        {"schema_version": 1, "currencies": []},  # Missing date
        {"schema_version": 1, "date": "invalid-date", "currencies": []},  # Invalid date format
        {"schema_version": 1, "date": "2026-10-19"},  # Missing currencies
        {"schema_version": 1, "date": "2026-10-19", "currencies": "not a list"},  # Currencies not list
        {
            "schema_version": 1,
            "date": "2026-10-19",
            "currencies": [{"code": "EUR", "name": "Euro", "nominal": -1, "value_mdl": "20"}],
        },  # Negative nominal
        {
            "schema_version": 1,
            "date": "2026-10-19",
            "currencies": [{"code": "EUR", "name": "Euro", "nominal": 1, "value_mdl": "-20"}],
        },  # Negative value
        {
            "schema_version": 1,
            "date": "2026-10-19",
            "currencies": [{"code": "EUR", "name": "Euro", "nominal": 1, "value_mdl": "abc"}],
        },  # Non-numeric value
        {
            "schema_version": 1,
            "date": "2026-10-19",
            "currencies": [
                {"code": "EUR", "name": "Euro", "nominal": 1, "value_mdl": "20"},
                {"code": "EUR", "name": "Euro Duplicate", "nominal": 1, "value_mdl": "20"},
            ],
        },  # Duplicate codes
    ],
)
def test_cache_invalid_schema_or_values_raises_invalid_cache(tmp_path: Path, bad_content):
    cache_file = tmp_path / "invalid.json"
    cache_file.write_text(json.dumps(bad_content), encoding="utf-8")

    cache = RateCache(cache_file=cache_file)
    with pytest.raises(InvalidCacheError):
        cache.load()


def test_cache_write_error_handling(tmp_path: Path, sample_rate_set: RateSet):
    # Pass a path that is an existing directory instead of a file
    dir_path = tmp_path / "as_dir"
    dir_path.mkdir()

    cache = RateCache(cache_file=dir_path)
    with pytest.raises(CacheWriteError):
        cache.save(sample_rate_set)


def test_get_default_cache_path():
    path = get_default_cache_path()
    assert isinstance(path, Path)
    assert path.name == "rates_cache.json"
