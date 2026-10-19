# Implementation Plan: BNM Currency Converter

**Branch**: `spec` | **Date**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-bnm-currency-converter/spec.md`

## Summary

Build a Python 3.12 desktop currency converter that retrieves official BNM XML rates,
normalizes currency rates against MDL while preserving source precision, and converts amounts
using `Decimal`. Keep the GUI separate from the non-GUI client, parser, cache, rate service,
conversion, and validation modules. Search backward for available rates, offer the persistent
last-successful response when the source is offline, and label every result with its actual rate
date and provenance.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Tkinter/ttk and Python standard library; `httpx` with a 10-second
timeout for BNM requests; `xml.etree.ElementTree` for XML; `decimal` for monetary arithmetic;
`json` for the local cache; `pytest` for unit tests

**Storage**: One JSON file in the current user's data directory, containing the last successful
rate set and its effective date

**Testing**: `python -m pytest`; unit tests for every GUI-independent module. Parser, conversion,
validation, and rate-service tests use known fixtures and fakes; no test depends on live BNM or
network availability.

**Target Platform**: Desktop platforms with Python 3.12 and Tk support; the current development
environment is Windows

**Project Type**: Single Python desktop application

**Performance Goals**: Bound each HTTP request to 10 seconds. Keep Tk event handling responsive
while network work is pending. When rates are already loaded, conversion results appear within
one second; validation completes within one second.

**Constraints**: No console UI; Tkinter is the only GUI toolkit. Use only standard-library
modules plus `httpx` and `pytest`. GUI-independent modules MUST NOT import GUI modules. Recoverable
network, parsing, and file errors MUST be shown clearly without terminating the application.
Source rates retain their full published precision; converted amounts use two decimal places and
half-up rounding. Offline cache use and date fallback must identify the actual effective date.

**Scale/Scope**: One local user, one conversion at a time, and the currencies published in one
BNM rate response. Charts, history, and accounts are excluded.

## Constitution Check

| Gate | Result | Evidence |
|---|---|---|
| Python desktop UI and dependency limits | PASS | Python 3.12, Tkinter/ttk, standard library, httpx, pytest |
| Separation of GUI and core responsibilities | PASS | Client, parser, cache, rate service, converter, and validation live outside `gui.py` |
| Error visibility and offline persistence | PASS | Explicit source/parser/cache errors; persistent cache and actual cached date in results |
| Decimal precision and rounding | PASS | Decimal throughout conversion; full source rate precision; half-up result rounding |
| Test-first and documented test command | PASS | Per-core-module pytest tests; `python -m pytest` documented in quickstart and required in README |
| Git workflow | PASS | Work follows the spec/implementation/tests stage branch workflow and PR-only merges in the constitution |

No constitution violations or unresolved design gates are identified.

## Project Structure

### Documentation (this feature)

```text
specs/001-bnm-currency-converter/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bnm-source.md
│   ├── rate-cache.md
│   └── user-interface.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── converter/
    ├── __init__.py
    ├── __main__.py
    ├── bnm_client.py
    ├── cache.py
    ├── converter.py
    ├── gui.py
    ├── parser.py
    ├── rates_service.py
    └── validation.py

tests/
├── test_bnm_client.py
├── test_cache.py
├── test_converter.py
├── test_parser.py
├── test_rates_service.py
└── test_validation.py

README.md
pyproject.toml
```

`gui.py` owns the Tkinter window, widget state, and user-facing messages. It calls `rates_service`,
`converter`, and `validation`; it does not parse XML, calculate rates, or read/write cache files.
Network requests run outside the Tk event loop, and GUI updates are marshalled back onto that
loop. `__main__.py` starts the desktop application without creating a console UI.

**Structure Decision**: Use the single-project `src/converter/` package and `tests/` layout
specified by the user. Keep I/O in `bnm_client.py` and `cache.py`; keep parsing, conversion, and
validation GUI-independent and deterministic. Use fakes for service tests and fixtures for parser
and conversion tests.

## Complexity Tracking

No constitution violations require justification.
