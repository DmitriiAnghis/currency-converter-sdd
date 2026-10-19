"""Tests for BNM HTTP client."""

from datetime import date
import httpx
import pytest

from converter.bnm_client import (
    BnmClient,
    DateUnavailableError,
    InvalidStatusError,
    SourceUnavailableError,
)


def test_bnm_client_url_and_date_formatting():
    recorded_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal recorded_request
        recorded_request = request
        return httpx.Response(200, text="<ValCurs Date='05.03.2026'></ValCurs>")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        result = client.fetch_rates(date(2026, 3, 5))

    assert recorded_request is not None
    assert recorded_request.url.scheme == "https"
    assert recorded_request.url.host == "www.bnm.md"
    assert recorded_request.url.path == "/en/official_exchange_rates"
    assert recorded_request.url.params["get_xml"] == "1"
    assert recorded_request.url.params["date"] == "05.03.2026"
    assert result == "<ValCurs Date='05.03.2026'></ValCurs>"


def test_bnm_client_timeout_configured():
    client = BnmClient()
    assert client.timeout == 10.0


def test_bnm_client_404_raises_date_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        with pytest.raises(DateUnavailableError, match="No rates available"):
            client.fetch_rates(date(2026, 10, 25))


def test_bnm_client_500_raises_source_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        with pytest.raises(SourceUnavailableError, match="server error"):
            client.fetch_rates(date(2026, 10, 19))


def test_bnm_client_403_raises_invalid_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        with pytest.raises(InvalidStatusError, match="403"):
            client.fetch_rates(date(2026, 10, 19))


def test_bnm_client_timeout_raises_source_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        with pytest.raises(SourceUnavailableError, match="timed out"):
            client.fetch_rates(date(2026, 10, 19))


def test_bnm_client_connect_error_raises_source_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BnmClient(http_client=http_client)
        with pytest.raises(SourceUnavailableError, match="[Nn]etwork|[Cc]onnect"):
            client.fetch_rates(date(2026, 10, 19))
