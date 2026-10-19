# BNM Currency Converter

Desktop currency converter with a graphical interface, using official exchange rates from the National Bank of Moldova (BNM).

## Features

- **Official BNM Rates**: Fetches official exchange rate XML documents from `bnm.md`.
- **Exact Decimal Arithmetic**: Performs monetary conversions and reverse rate calculations using Python's `decimal.Decimal` with standard half-up rounding on final converted amounts. Full source precision is preserved.
- **Support for All BNM Currencies**: Supports MDL as the base currency and every currency returned by BNM, properly normalizing nominal quantities (e.g., 10 or 100 units). Popular currencies (EUR, USD, RON, UAH, RUB, GBP) are listed first.
- **Ten-Calendar-Day Date Lookback**: When no rates are published for a selected date (e.g., weekends, holidays, or future dates), the application searches backward one calendar day at a time up to 10 days earlier and clearly reports the actual effective date used.
- **Resilient Offline Cache**: Automatically saves the last successful rate response to a versioned JSON file in the operating system's per-user data directory (`%APPDATA%` on Windows, `~/Library/Application Support` on macOS, and `$XDG_DATA_HOME` on Linux). When offline, the app offers the user the explicit choice to use saved rates with clear provenance and date labelling.
- **Input Validation**: Accepts positive numbers with either comma `,` or period `.` decimal separators. Rejects empty, zero, negative, alphabetic, mixed-separator, and malformed inputs with clear feedback.
- **Responsive GUI**: Uses a dedicated background worker thread for network operations, ensuring the window remains interactive and responsive at all times without freezing.

## Prerequisites

- Python 3.12 or newer with Tkinter support (`tk.TkVersion >= 8.6`).

## Installation

From the repository root, install the dependencies and package in editable mode:

```powershell
python -m pip install httpx pytest
python -m pip install -e .
```

Alternatively, expose `src` via `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
```

## Running the Application

To launch the desktop GUI (without console UI):

```powershell
python -m converter
```

## Running Tests

To run the complete test suite:

```powershell
python -m pytest
```

All unit tests execute deterministically without relying on network access or live BNM availability.

## Project Structure

```text
src/
└── converter/
    ├── __init__.py         # Package initialization
    ├── __main__.py         # Desktop application entry point
    ├── bnm_client.py       # HTTP client with 10s timeout and error handling
    ├── cache.py            # Versioned JSON cache in per-user data directory
    ├── converter.py        # Monetary arithmetic using Decimal
    ├── gui.py              # Tkinter desktop interface
    ├── parser.py           # BNM XML exchange rate parser
    ├── rates_service.py    # Service orchestrating date fallback & cache
    └── validation.py       # Amount validation and parsing

tests/
├── conftest.py             # Shared pytest fixtures and Tk setup
├── fixtures/
│   └── bnm_rates.xml       # Sample BNM XML exchange rates fixture
├── test_bnm_client.py      # HTTP client and error classification tests
├── test_cache.py           # JSON cache round-trip, precision & schema tests
├── test_converter.py       # Arithmetic, cross-currency & nominal unit tests
├── test_gui.py             # GUI interaction, currency ordering & notice tests
├── test_parser.py          # XML parser, required fields & duplicate tests
├── test_rates_service.py   # Rate retrieval, 10-day lookback & offline tests
└── test_validation.py      # Input parsing, separators & form state tests
```
