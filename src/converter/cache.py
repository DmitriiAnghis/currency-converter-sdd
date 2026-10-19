"""Persistent versioned JSON cache for official BNM exchange rates."""

from datetime import date
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import sys
from typing import Optional

from converter.parser import Currency, RateSet, MDL_CURRENCY


CURRENT_SCHEMA_VERSION = 1


class CacheError(Exception):
    """Base exception for cache operations."""
    pass


class InvalidCacheError(CacheError):
    """Raised when the cache file contains corrupted or invalid data."""
    pass


class CacheWriteError(CacheError):
    """Raised when saving to the cache file fails."""
    pass


def get_default_cache_path() -> Path:
    """Resolve the platform-specific user data directory for cache storage."""
    app_folder = "BnmCurrencyConverter"
    filename = "rates_cache.json"

    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"

    return base / app_folder / filename


class RateCache:
    """Manages reading and writing of versioned exchange rate cache files."""

    def __init__(self, cache_file: Optional[Path] = None) -> None:
        self.cache_file = cache_file if cache_file is not None else get_default_cache_path()

    def load(self) -> Optional[RateSet]:
        """Load and validate the cached RateSet.

        Returns:
            RateSet if cache exists and is valid, None if cache file does not exist.

        Raises:
            InvalidCacheError: If cache content is corrupted, unreadable, or invalid.
        """
        if not self.cache_file.exists():
            return None

        try:
            raw_text = self.cache_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise InvalidCacheError(f"Cannot read cache file: {exc}") from exc

        try:
            data = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise InvalidCacheError(f"Unreadable or corrupted JSON in cache file: {exc}") from exc

        if not isinstance(data, dict):
            raise InvalidCacheError("Invalid cache structure: root must be a JSON object")

        schema_version = data.get("schema_version")
        if schema_version != CURRENT_SCHEMA_VERSION:
            raise InvalidCacheError(
                f"Unsupported cache schema version {schema_version}, expected {CURRENT_SCHEMA_VERSION}"
            )

        raw_date = data.get("date")
        if not raw_date or not isinstance(raw_date, str):
            raise InvalidCacheError("Missing or invalid 'date' in cache file")

        try:
            effective_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise InvalidCacheError(f"Invalid ISO date '{raw_date}' in cache file") from exc

        raw_currencies = data.get("currencies")
        if not isinstance(raw_currencies, list):
            raise InvalidCacheError("Invalid 'currencies' field in cache: must be a list")

        currencies: dict[str, Currency] = {}

        for item in raw_currencies:
            if not isinstance(item, dict):
                raise InvalidCacheError("Invalid currency entry in cache: must be an object")

            code = item.get("code")
            name = item.get("name")
            nominal = item.get("nominal")
            value_mdl_str = item.get("value_mdl")

            if not code or not isinstance(code, str):
                raise InvalidCacheError("Missing or invalid 'code' in cache currency record")
            if code in currencies:
                raise InvalidCacheError(f"Duplicate currency code '{code}' in cache file")
            if not name or not isinstance(name, str):
                raise InvalidCacheError(f"Missing or invalid 'name' for currency '{code}'")

            if not isinstance(nominal, int) or nominal <= 0:
                raise InvalidCacheError(f"Invalid nominal '{nominal}' for currency '{code}', must be positive int")

            if not isinstance(value_mdl_str, str):
                raise InvalidCacheError(f"Invalid value_mdl for currency '{code}', must be a decimal string")

            try:
                value_mdl = Decimal(value_mdl_str)
                if value_mdl <= 0 or not value_mdl.is_finite():
                    raise ValueError()
            except (InvalidOperation, ValueError) as exc:
                raise InvalidCacheError(f"Invalid value_mdl '{value_mdl_str}' for currency '{code}'") from exc

            currencies[code] = Currency(
                code=code,
                name=name,
                nominal=nominal,
                value_mdl=value_mdl,
            )

        if "MDL" not in currencies:
            currencies["MDL"] = MDL_CURRENCY

        return RateSet(
            date=effective_date,
            currencies=currencies,
            source="cache",
            is_cached=True,
            notice="Using offline saved rates.",
        )

    def save(self, rate_set: RateSet) -> None:
        """Persist a successful RateSet to the cache file.

        Raises:
            CacheWriteError: If writing to the cache file fails.
        """
        records = []
        for curr in rate_set.currencies.values():
            records.append({
                "code": curr.code,
                "name": curr.name,
                "nominal": curr.nominal,
                "value_mdl": str(curr.value_mdl),
            })

        payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "date": rate_set.date.isoformat(),
            "currencies": records,
        }

        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise CacheWriteError(f"Failed to write cache file to {self.cache_file}: {exc}") from exc
