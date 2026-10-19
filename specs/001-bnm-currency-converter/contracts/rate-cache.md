# Local Rate Cache Contract

## Purpose

Persist only the last successfully fetched and parsed BNM rate set so it can be offered for an
offline conversion after restart.

## Record

The JSON document contains:

- `schema_version`: positive integer identifying the cache format.
- `date`: effective rate date in ISO `YYYY-MM-DD` format.
- `currencies`: list of records, each containing `code`, `name`, `nominal`, and `value_mdl`.
- Decimal values are serialized as decimal strings to preserve precision.

MDL is derived as the base currency with nominal 1 and value 1; it may be included in the record
or reconstructed on load, but consumers must observe exactly one MDL currency at rate 1.

## Write behavior

- Save only after a valid, non-empty online rate set has been parsed.
- Replace the previous cache as one complete document; do not save partial data.
- A failed fetch or invalid response must not overwrite the previous successful record.
- Cache write failures are reported clearly and must not crash the application.

## Read behavior

- Validate the schema version, date, required fields, unique currency codes, positive nominal
  values, and positive finite decimal rates before returning a cache entry.
- Missing cache is a normal cache-miss state.
- Unreadable JSON or invalid cache contents produce a clear message and are not used for
  conversion.
- When the cache is offered or used, display its effective date and label its provenance as
  `cache from DD.MM.YYYY`.

## Location

Store one cache file under the operating system's per-user data directory using standard-library
path resolution:

- Windows: `%APPDATA%` when set.
- macOS: `~/Library/Application Support`.
- Linux: `$XDG_DATA_HOME` when set, otherwise `~/.local/share`.

Place the cache in an application-specific subdirectory and use a stable JSON filename. If a
required platform location cannot be resolved or accessed, report the file error clearly; do not
silently switch to a different location.
