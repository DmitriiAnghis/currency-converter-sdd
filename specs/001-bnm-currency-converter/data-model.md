# Data Model: BNM Currency Converter

## Currency

Represents one selectable currency in a rate set.

| Field | Type | Rules |
|---|---|---|
| `code` | string | Required ISO-like BNM `CharCode`; unique within one rate set |
| `name` | string | Required source name |
| `nominal` | positive integer | Published number of currency units represented by `value`; MDL uses 1 |
| `value_mdl` | Decimal | Positive MDL value for `nominal` units; MDL uses 1 |
| `unit_rate_mdl` | Decimal | `value_mdl / nominal`; MDL uses 1 |

The rate parser creates a currency record from BNM `CharCode`, `Name`, `Nominal`, and `Value`.
Source decimal text is parsed directly to `Decimal`; no binary floating point is used.

## RateSet

Represents the rates applicable on a specific effective date.

| Field | Type | Rules |
|---|---|---|
| `date` | date | Effective rate date from the BNM response or the saved cache |
| `currencies` | mapping from code to Currency | Includes MDL and all valid currencies from the response; codes are unique |
| `source` | enum: `bnm`, `cache` | Provenance of the data currently used |
| `is_cached` | boolean | True only when the user accepted cached data |
| `notice` | optional string | User-visible fallback or source notice; empty when no notice is needed |

BNM data is parsed and validated before it is saved or exposed for conversion. A response without
usable rates is not considered a successful rate set.

## RatesResult

Represents a completed rate lookup suitable for display and conversion.

| Field | Type | Rules |
|---|---|---|
| `rates` | RateSet | Rates selected for this conversion |
| `date` | date | Same as `rates.date`; never substitute the requested date when another date was found |
| `source` | enum: `bnm`, `cache` | Same provenance as `rates.source` |
| `is_cached` | boolean | Same cached status as `rates.is_cached` |
| `notice` | optional string | Explains fallback date or cache use when applicable |

The service checks the requested date first and then up to ten calendar days earlier. The first
date with valid rates wins. A source-unavailable error is distinct from a date with no rates; on
source unavailability, cached rates are offered rather than silently used.

## Conversion

Represents the displayed result for a user-entered amount and selected currencies.

| Field | Type | Rules |
|---|---|---|
| `amount` | Decimal | Must be greater than zero |
| `from_code` | string | Must identify a currency in the selected RateSet |
| `to_code` | string | Must identify a currency in the selected RateSet |
| `result` | Decimal | `amount * source.unit_rate_mdl / target.unit_rate_mdl`, rounded once to 0.01 with `ROUND_HALF_UP` |
| `reverse_rate` | Decimal | `target.unit_rate_mdl / source.unit_rate_mdl`, expressed in source units per one target unit |
| `rate_date` | date | Effective date of the RateSet used |
| `source` | enum: `bnm`, `cache` | Provenance of the RateSet used |

When `from_code` equals `to_code`, the result equals the input amount and the reverse rate is 1.

## Amount validation

- Accept a positive decimal string using either `,` or `.` as its sole decimal separator.
- Convert a single comma decimal separator to the internal decimal representation.
- Reject empty input, zero, negative amounts, alphabetic input, multiple decimal separators, or
  input containing both comma and period.
- Validation failure produces a user-visible message and no Conversion.

## Cache record

The persisted record contains a schema version, effective date, and all currency fields needed
to recreate one RateSet. It is validated on load; invalid or unreadable cache data produces a
clear error and is never used as a successful result.

## State transitions

1. **Requested**: The GUI submits amount, currency selections, and requested rate date.
2. **Fetching**: The service checks dates in order, up to the selected date plus ten days prior.
3. **Available**: A valid online RateSet is returned and saved as the last successful data.
4. **No rates for date**: The service advances to the preceding date until rates are found or
   the lookback limit is reached.
5. **Source unavailable**: The GUI shows the source error and, if valid cache exists, asks whether
   to use the cached RateSet.
6. **Cache accepted**: The conversion proceeds with the cache's actual effective date and cache
   provenance displayed.
7. **Invalid input or data**: No conversion is produced; the GUI displays a clear validation,
   parsing, or cache error.
