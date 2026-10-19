# Research: BNM Currency Converter

## BNM XML source

**Decision**: Request the official BNM endpoint with a `date=DD.MM.YYYY` parameter:
`https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=DD.MM.YYYY`.

**Rationale**: The date format is accepted by BNM's official source. The response uses a
`<ValCurs Date="…" name="Official exchange rate">` root and repeated `<Valute>` entries with
`CharCode`, `Nominal`, `Name`, and `Value` children. The source date is the rate set's effective
date.

**Alternatives considered**: ISO or slash-separated dates were tried against the same endpoint;
both returned HTTP 404. Do not send those formats.

**Evidence**: BNM's [official XML response for 19 October 2026](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=19.10.2026).

## Rate normalization

**Decision**: Represent each currency's per-unit rate against MDL as `Value / Nominal`, using
`Decimal` values constructed from source text. MDL has a per-unit rate of 1.

**Rationale**: BNM's `Value` is the MDL amount for the published `Nominal` units. For example,
the 19 October response lists ALL with nominal 10 and value 2.2010, meaning 10 ALL = 2.2010 MDL.
For conversion, multiply the source amount by the source per-unit MDL rate, then divide by the
target per-unit MDL rate. Do not round rates before conversion.

**Alternatives considered**: Treating `Value` as the value of one unit is incorrect for currencies
with nominal quantities greater than one. Rounding normalized rates would discard source
precision.

**Evidence**: BNM's [official XML response for 19 October 2026](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=19.10.2026).

## Dates without available rates

**Decision**: Continue the date fallback when BNM indicates that the requested date has no
available rate document (including the observed HTTP 404 response); treat transport failures and
server errors as source-unavailable errors and offer the cache. Treat a successful but empty
rate set as no rates for that date. Treat malformed XML or structurally invalid rates as invalid
source data, not as an empty date.

**Rationale**: The observed endpoint returned HTTP 404 for an out-of-range date, while a Sunday
request returned populated XML. Mapping every non-success response to a network failure would
prevent date fallback for unavailable dates. Conversely, hiding transport/server errors as empty
dates could obscure an outage.

**Alternatives considered**: Assuming weekends always return empty XML is not supported by the
observed Sunday response. Treating every non-2xx response as a date without rates would also hide
server-side and connectivity failures.

**Evidence and limit**: BNM's [out-of-range date response](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=25.10.2026) returned HTTP 404; a
[Sunday response](https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=18.10.2026) returned populated XML. An empty valid `<ValCurs>` response was not verified; its handling above is the conservative rule required by the feature.

## HTTP client and GUI responsiveness

**Decision**: Use `httpx` with a 10-second timeout, injected or replaceable at the rate-service
boundary for tests. Run requests away from Tk's event loop and deliver results/errors back to Tk
through its event queue.

**Rationale**: A bounded request prevents indefinite waits; running it off the UI event loop
prevents the window from freezing during the allowed timeout. UI widgets remain owned and updated
by the Tk thread.

**Alternatives considered**: A synchronous request on the Tk thread is simpler but can block the
interface for up to the entire timeout. A separate asynchronous HTTP framework is unnecessary
for one local desktop application and conflicts with the small dependency budget.

## XML parsing

**Decision**: Parse source XML with `xml.etree.ElementTree`; reject malformed documents, missing
required fields, non-positive nominal values, invalid decimals, duplicate currency codes, or an
otherwise unusable rate set with explicit parser errors. An empty valid rate set is a distinct
no-rates outcome.

**Rationale**: The standard library parser meets the source format without introducing a
dependency. Keeping malformed data distinct from a valid no-rate date enables clear user errors
and prevents overwriting a good cache with invalid data.

**Alternatives considered**: A third-party XML parser adds an unnecessary dependency. Treating
malformed XML as an empty rate set could silently cause incorrect fallback behavior.

## Cache storage

**Decision**: Persist the last successfully parsed source rate set and its effective date as
versioned JSON in the user's data directory. Write only after a successful fetch and parse. On
cache load, validate the document and values before exposing them to conversion.

**Rationale**: JSON and user-scoped paths satisfy restart persistence without external storage
dependencies. A clear schema permits detection of stale or corrupted cache files, and updating
only after validation preserves the last known-good rates.

**Alternatives considered**: Keeping cache only in memory does not survive restarts. A database is
unnecessary for a single last-successful rate set.

For the user data directory, use `APPDATA` on Windows when set, `~/Library/Application Support`
on macOS, and `XDG_DATA_HOME` or `~/.local/share` on Linux. Resolve the path with standard-library
`os` and `pathlib`; do not add a platform-directory dependency.

## Amounts and rounding

**Decision**: Parse user input as `Decimal`, accepting one comma or period decimal separator but
no grouping separators. Reject empty, malformed, zero, and negative amounts. Round only the final
converted amount to two decimal places with `ROUND_HALF_UP`.

**Rationale**: Decimal arithmetic avoids binary floating-point errors and matches the specified
money behavior. A single separator rule avoids guessing whether mixed punctuation is grouping or
decimal notation.

**Alternatives considered**: Binary floats can yield precision errors. Rounding intermediate
rates or cross-rate calculations can compound errors.

## Test strategy and packaging

**Decision**: Test every GUI-independent module with pytest, use deterministic parser fixtures
and fake client/cache collaborators, and document `python -m pytest` and `python -m converter`.
Keep tests independent of live network access.

**Rationale**: Fakes exercise offline, fallback, and failure paths deterministically; the
prescribed commands make testing and launching discoverable.

**Alternatives considered**: Live BNM requests in unit tests are nondeterministic and depend on
network availability. GUI-driven integration is not a substitute for pure core tests.

## Constitution review

The selected stack stays within Python 3.12, Tkinter, the standard library, `httpx`, and pytest.
Core responsibilities remain separated, errors are surfaced, the on-disk cache is retained
between runs, and conversion uses `Decimal`. These choices satisfy the applicable constitutional
gates.
