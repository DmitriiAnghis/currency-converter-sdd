"""HTTP client for retrieving official exchange rates from BNM."""

from datetime import date
from typing import Optional
import httpx


BNM_BASE_URL = "https://www.bnm.md/en/official_exchange_rates"
DEFAULT_TIMEOUT = 10.0


class BnmClientError(Exception):
    """Base exception for BNM client errors."""
    pass


class DateUnavailableError(BnmClientError):
    """Raised when rates are unavailable for the requested date (e.g. HTTP 404)."""
    pass


class SourceUnavailableError(BnmClientError):
    """Raised when the BNM source cannot be reached (transport error, timeout, 5xx)."""
    pass


class InvalidStatusError(BnmClientError):
    """Raised when BNM returns an unexpected non-404 error status (e.g. 400, 403)."""
    pass


class BnmClient:
    """Client for fetching official exchange rates from BNM."""

    def __init__(
        self,
        http_client: Optional[httpx.Client] = None,
        base_url: str = BNM_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._http_client = http_client
        self.base_url = base_url
        self.timeout = timeout

    def fetch_rates(self, target_date: date) -> str:
        """Fetch the XML rate document for target_date from BNM.

        Raises:
            DateUnavailableError: If BNM returns 404 (no document published for date).
            SourceUnavailableError: If network fails, request times out, or server error (5xx).
            InvalidStatusError: If BNM returns other non-2xx status code.
        """
        date_str = target_date.strftime("%d.%m.%Y")
        params = {"get_xml": "1", "date": date_str}

        client = self._http_client
        client_context = None
        if client is None:
            client_context = httpx.Client(timeout=self.timeout)
            client = client_context

        try:
            response = client.get(self.base_url, params=params, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError(f"Request to BNM timed out after {self.timeout}s: {exc}") from exc
        except httpx.TransportError as exc:
            raise SourceUnavailableError(f"Network transport error connecting to BNM: {exc}") from exc
        except Exception as exc:
            raise SourceUnavailableError(f"Unexpected error communicating with BNM: {exc}") from exc
        finally:
            if client_context is not None:
                client_context.close()

        if response.status_code == 404:
            raise DateUnavailableError(f"No rates available for {date_str} (HTTP 404)")

        if 500 <= response.status_code < 600:
            raise SourceUnavailableError(f"BNM server error: HTTP {response.status_code}")

        if response.status_code != 200:
            raise InvalidStatusError(f"Unexpected HTTP status {response.status_code} from BNM")

        return response.text
