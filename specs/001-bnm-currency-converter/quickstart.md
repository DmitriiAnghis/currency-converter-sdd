# Quickstart: BNM Currency Converter

## Prerequisites

- Python 3.12 with Tk support available.
- Network access for fresh rates from BNM (optional when a saved rate set is available).

## Setup

From the repository root, install the permitted runtime and test dependencies:

```powershell
python -m pip install httpx pytest
```

Expose the `src` package to Python for local source-tree execution:

```powershell
$env:PYTHONPATH = "src"
```

The application entry point is:

```powershell
python -m converter
```

The full unit-test suite is:

```powershell
python -m pytest
```

The project README must document the test command and user-facing launch instructions.

## Validation scenarios

1. With network access, launch the GUI, enter `100`, choose EUR and MDL, convert, and confirm
   the result, reverse rate, effective BNM date, and `BNM, official rate for DD.MM.YYYY` label.
2. Convert between EUR and USD in both directions and compare results to the rates normalized by
   each published nominal quantity.
3. Choose the same currency in both selectors and confirm the amount is unchanged and the reverse
   rate is 1.
4. Enter `100,50` and `100.50`; confirm both are accepted. Try empty, zero, negative, alphabetic,
   and mixed-separator inputs; confirm no result is produced and a clear validation message is
   shown.
5. Choose a date with no published response and confirm the app selects the first available date
   while checking back no more than ten days, and displays the actual rate date.
6. After a successful fetch, disconnect the network and request rates again. Confirm a clear
   source error and a dated cache-use offer; accept it and verify the result says
   `cache from DD.MM.YYYY`.
7. Restart the app while offline and confirm the same last successful rate set remains available.
8. Run `python -m pytest` with network access disabled; all tests should pass using fixtures and
   fakes without making live requests.

For entity and validation rules, see [data-model.md](./data-model.md). For the BNM request and
response behavior, see [contracts/bnm-source.md](./contracts/bnm-source.md) and for persistent
cache behavior see [contracts/rate-cache.md](./contracts/rate-cache.md). The user-visible form,
result, and error behavior is defined in [contracts/user-interface.md](./contracts/user-interface.md).
