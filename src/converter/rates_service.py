"""Service coordinating rate retrieval, date fallback, and caching."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from converter.bnm_client import (
    BnmClient,
    BnmClientError,
    DateUnavailableError,
    SourceUnavailableError,
)
from converter.parser import (
    EmptyResponse,
    InvalidResponse,
    RateSet,
    parse_bnm_xml,
)


class RatesServiceError(Exception):
    """Base exception for rates service errors."""
    pass


class NoRatesFoundError(RatesServiceError):
    """Raised when no rates are available for the requested search period."""
    pass


class InvalidDataError(RatesServiceError):
    """Raised when rate data from source or cache is corrupted or malformed."""
    pass


@dataclass
class RatesResult:
    """Represents the outcome of a rate lookup."""
    rates: RateSet
    date: date
    source: str = "bnm"
    is_cached: bool = False
    notice: Optional[str] = None

    @property
    def provenance_label(self) -> str:
        """Formatted provenance string as required by contracts."""
        date_str = self.date.strftime("%d.%m.%Y")
        if self.source == "bnm":
            return f"BNM, official rate for {date_str}"
        return f"cache from {date_str}"


class RatesService:
    """Service providing official rates with date fallback and offline cache support."""

    def __init__(
        self,
        client: Optional[BnmClient] = None,
        cache: Optional[Any] = None,
    ) -> None:
        self.client = client if client is not None else BnmClient()
        self.cache = cache

    def get_rates(self, target_date: date) -> RatesResult:
        """Retrieve rates for target_date.

        In Phase 4, retrieves rates for a single date.
        Extended in Phase 5 for 10-day fallback and in Phase 6 for offline cache.
        """
        try:
            xml_text = self.client.fetch_rates(target_date)
        except DateUnavailableError as exc:
            raise NoRatesFoundError(f"No rates found for {target_date.strftime('%d.%m.%Y')}") from exc
        except SourceUnavailableError:
            raise

        try:
            rate_set = parse_bnm_xml(xml_text)
        except EmptyResponse as exc:
            raise NoRatesFoundError(f"No rates found in response for {target_date.strftime('%d.%m.%Y')}") from exc
        except InvalidResponse as exc:
            raise InvalidDataError(f"Malformed or invalid rate data: {exc}") from exc

        # Save to cache if cache is provided
        if self.cache is not None:
            try:
                self.cache.save(rate_set)
            except Exception:
                # Log or ignore cache save failure so conversion still succeeds
                pass

        return RatesResult(
            rates=rate_set,
            date=rate_set.date,
            source="bnm",
            is_cached=False,
            notice=None,
        )
