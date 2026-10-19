"""Service coordinating rate retrieval, date fallback, and caching."""

from dataclasses import dataclass
from datetime import date, timedelta
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
        """Retrieve rates for target_date or up to 10 earlier calendar dates.

        Checks target_date and then steps backward one calendar day at a time, up
        to 10 days earlier. Uses the first valid non-empty rate set found.

        Raises:
            NoRatesFoundError: If no rates are found in the 10-day lookback period.
            InvalidDataError: If the source returns malformed XML or invalid data.
            SourceUnavailableError: If the BNM source cannot be reached.
        """
        for offset in range(11):
            check_date = target_date - timedelta(days=offset)
            try:
                xml_text = self.client.fetch_rates(check_date)
            except DateUnavailableError:
                # 404: date has no rates, continue to earlier date
                continue
            except SourceUnavailableError:
                # Network or server failure: do not continue fallback
                raise

            try:
                rate_set = parse_bnm_xml(xml_text)
            except EmptyResponse:
                # Valid XML with 0 Valute entries: continue to earlier date
                continue
            except InvalidResponse as exc:
                # Malformed XML or structurally invalid rates: report error immediately
                raise InvalidDataError(f"Malformed or invalid rate data from BNM: {exc}") from exc

            # Valid rate set found!
            notice = None
            if offset > 0:
                notice = (
                    f"No rates published for {target_date.strftime('%d.%m.%Y')}; "
                    f"using official rates from {rate_set.date.strftime('%d.%m.%Y')}."
                )

            # Persist to cache if cache is configured
            if self.cache is not None:
                try:
                    self.cache.save(rate_set)
                except Exception:
                    pass

            return RatesResult(
                rates=rate_set,
                date=rate_set.date,
                source="bnm",
                is_cached=False,
                notice=notice,
            )

        raise NoRatesFoundError(
            f"No rates found for {target_date.strftime('%d.%m.%Y')} or the 10-day lookback period."
        )
