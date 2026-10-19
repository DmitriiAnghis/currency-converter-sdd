# BNM Rate Source Contract

## Request

- **Method**: HTTP GET
- **URL**: `https://www.bnm.md/en/official_exchange_rates`
- **Query**: `get_xml=1` and `date=DD.MM.YYYY` (zero-padded day and month)
- **Timeout**: 10 seconds

## Successful response

- A successful response body is XML with a `<ValCurs>` root and zero or more `<Valute>` entries.
- The root `Date` attribute is the effective date reported by the source.
- Each usable `<Valute>` contains `CharCode`, `Name`, `Nominal`, and `Value`.
- `Value` is the MDL amount for `Nominal` units. Normalize one unit as
  `Decimal(Value) / Decimal(Nominal)`.
- The application adds MDL with nominal 1 and per-unit rate 1.
- A non-empty valid response for the requested date is the online rate set. An empty valid rate
  set means no rates are available for that date.

## Response handling

- HTTP 404 observed from BNM for a date without an available document is treated as no rates for
  that date so date fallback can continue.
- Transport errors, timeouts, and server errors are source-unavailable errors. The GUI reports
  the failure and offers the last successful cache if present.
- Other unsuccessful HTTP status codes are reported as source errors, not parsed as rates.
- Malformed XML, missing required fields, invalid numeric values, duplicate codes, or non-positive
  nominal/value data are invalid responses. Report the parsing/data error and do not overwrite the
  last successful cache.
- A syntactically valid but empty rate set is distinct from malformed or unavailable source data.

## Date fallback

Check the selected date first, then each prior calendar date in order, through ten days earlier.
Use the first valid non-empty rate set returned. Report the actual effective date and do not
present a fallback date as the requested date.

## Source evidence

The observed [BNM response for 19 October 2026](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=19.10.2026)
contains the documented fields. An [out-of-range date](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=25.10.2026)
returned HTTP 404, while a [Sunday date](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=18.10.2026)
returned populated XML. Empty valid XML behavior was not verified; handling it as no rates follows
the feature's date-fallback requirement.
