# Tasks: BNM Currency Converter

**Input**: Design documents from `specs/001-bnm-currency-converter/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/`

**Tests**: Required. The constitution and feature specification require pytest unit tests for
every GUI-independent core module. Write each module's tests before its implementation; use
fixtures and fakes, never live network access.

**Organization**: Tasks are grouped by the four user stories in `spec.md`. The two P1 stories are
ordered with input validation first because valid input is a prerequisite for safely converting.

## Format

Every task uses `- [ ] TNNN [P?] [USn?] Description with file path`. `[P]` appears only for work
that can proceed independently in a different file; story labels appear only in user-story
phases.

## Phase 1: Setup

**Purpose**: Establish the package, dependency declaration, and shared test data.

- [x] T001 [P] Configure Python 3.12 packaging, `httpx` runtime dependency, pytest test dependency, and `src` package discovery in `pyproject.toml`
- [x] T002 [P] Create the importable package initializer in `src/converter/__init__.py`

## Phase 2: Foundational

**Purpose**: Provide deterministic BNM input data shared by parser and service tests.

- [x] T003 Add a representative BNM XML fixture with EUR and a non-unit nominal currency to `tests/fixtures/bnm_rates.xml`

**Checkpoint**: Setup and shared fixture are ready; user-story work can begin.

## Phase 3: User Story 4 - Correct Invalid Amounts (Priority: P1)

**Goal**: Reject invalid amounts, show useful feedback, and prevent conversion until amount and
both currency selections are present.

**Independent Test**: Run `python -m pytest tests/test_validation.py`; verify empty, zero,
negative, alphabetic, malformed, comma-decimal, and period-decimal cases, then verify the form
enables conversion only after all required fields are filled.

### Tests for User Story 4

- [x] T004 [US4] Write `Decimal` parsing tests for empty, zero, negative, alphabetic, malformed, comma-decimal, and period-decimal inputs in `tests/test_validation.py`

### Implementation for User Story 4

- [x] T005 [US4] Implement `parse_amount` and `ValidationError` in `src/converter/validation.py`; accept a positive decimal using one comma or period and reject empty, zero, negative, mixed-separator, multiple-separator, and non-numeric input
- [x] T006 [US4] Build the initial amount field, currency selectors, disabled-until-complete Convert button, and visible validation feedback using `parse_amount` in `src/converter/gui.py`

**Checkpoint**: Invalid amounts produce visible validation feedback and cannot produce a
conversion; incomplete form fields keep Convert disabled.

## Phase 4: User Story 1 - Convert an Amount (Priority: P1) 🎯 MVP

**Goal**: Convert supported currencies using BNM rates, displaying the result, reverse rate, rate
date, and provenance.

**Independent Test**: With the BNM client replaced by a deterministic response, run
`python -m pytest tests/test_parser.py tests/test_bnm_client.py tests/test_converter.py tests/test_rates_service.py`;
verify same-currency, MDL/EUR, EUR/USD, and nominal-quantity conversions. Launch
`python -m converter` and verify the full conversion form and result.

### Tests for User Story 1

- [x] T007 [P] [US1] Test BNM XML parsing, required fields, decimal precision, duplicate currency codes, empty response, and malformed XML in `tests/test_parser.py`
- [x] T008 [P] [US1] Test BNM request URL/date formatting, 10-second timeout, status handling, and transport failures with a fake HTTP client in `tests/test_bnm_client.py`
- [x] T009 [P] [US1] Test same-currency, MDL-to-EUR, EUR-to-MDL, EUR-to-USD in both directions, and nominal 10/100 arithmetic in `tests/test_converter.py`
- [x] T010 [US1] Test single-date rate retrieval, `RatesResult` date/provenance, and service handling of empty versus malformed responses with fake client and parser collaborators in `tests/test_rates_service.py`

### Implementation for User Story 1

- [x] T011 [US1] Implement the `Rate` data shape and XML parser in `src/converter/parser.py`; enforce `code`: "Required ISO-like BNM `CharCode`; unique within one rate set", `name`: "Required source name", `nominal`: "positive integer", and `value_mdl`: "Positive MDL value for `nominal` units", preserve source precision, and distinguish `EmptyResponse` from `InvalidResponse`
- [x] T012 [US1] Implement `BnmClient` in `src/converter/bnm_client.py` using the BNM `DD.MM.YYYY` URL, `httpx` timeout of 10 seconds, and distinct date-unavailable, source-unavailable, and invalid-status errors
- [x] T013 [US1] Implement `convert` in `src/converter/converter.py` using `Decimal`, requiring source and target codes to identify currencies in the selected rate set, `Value / Nominal` per-unit MDL rates, half-up rounding only on the final amount, and an unrounded reverse rate as source units per target unit
- [x] T014 [US1] Implement the initial one-date `RatesResult` flow in `src/converter/rates_service.py`, returning valid rates for the requested date and surfacing no-rate, source, and invalid-data outcomes distinctly
- [x] T015 [US1] Complete `src/converter/gui.py` with a Tkinter date selector defaulting to today, BNM currency choices ordered EUR/USD/RON/UAH/RUB/GBP first when present, background rate loading, conversion submission, result formatting, reverse-rate display to four decimals with half-up rounding, and actual BNM date/provenance display; on malformed source data show a clear error and suppress/clear the conversion result, and during a simulated 10-second request keep repainting and accept amount edits within 1 second
- [x] T016 [US1] Add the Tk application entry point without a console UI in `src/converter/__main__.py`

**Checkpoint**: The user can perform a valid online conversion and sees the actual BNM rate date
and source; all currency-independent calculation and parsing behavior is covered by unit tests.

## Phase 5: User Story 2 - Select a Rate Date (Priority: P2)

**Goal**: Use requested-date rates when available, otherwise search backward through the
ten-calendar-day lookback and explicitly report the effective date.

**Independent Test**: Run `python -m pytest tests/test_rates_service.py`; with fake rates for
selected dates, verify selected-date success, first prior available date, HTTP 404 date fallback,
ten-day boundary, no-rate exhaustion, and malformed response reporting.

### Tests for User Story 2

- [ ] T017 [US2] Add fake-client tests for requested-date success, one-day-at-a-time fallback, HTTP 404 fallback, exactly ten days of lookback, exhaustion, and malformed data in `tests/test_rates_service.py`

### Implementation for User Story 2

- [ ] T018 [US2] Extend `src/converter/rates_service.py` to check the selected date and then up to ten earlier calendar dates, treating BNM HTTP 404 and valid empty rate sets as no-rates dates, stopping at the first valid set, and returning the actual date plus a fallback notice
- [ ] T019 [US2] Update `src/converter/gui.py` to display the fallback notice and actual effective date, and to report lookback exhaustion without displaying a conversion

**Checkpoint**: Date lookup uses the first available date in the specified window and never
mislabels it as the requested date.

## Phase 6: User Story 3 - Convert Without a Network Connection (Priority: P2)

**Goal**: Persist the last successful rate response and explicitly offer it after source
unavailability without silently substituting cached values.

**Independent Test**: Run `python -m pytest tests/test_cache.py tests/test_rates_service.py`;
verify cache round-tripping across a reload, cache validation, preservation after failed fetches,
offline offer/decline/accept behavior, and cache date/provenance reporting.

### Tests for User Story 3

- [ ] T020 [P] [US3] Test JSON cache round-trip, decimal-string precision, schema/date/value validation, missing-file behavior, and read/write errors in `tests/test_cache.py`
- [ ] T021 [US3] Add service tests for saving only successful responses, offline with and without cache, explicit cached-rate acceptance, and preserving the cached effective date in `tests/test_rates_service.py`

### Implementation for User Story 3

- [ ] T022 [US3] Implement the versioned JSON cache and user-data path resolution in `src/converter/cache.py`; require `schema_version`, ISO effective `date`, and currency `code`, `name`, `nominal`, and `value_mdl` fields; enforce unique codes, positive integer nominal, and positive finite values; serialize decimals as strings to preserve precision; treat missing cache as a miss and report invalid/unreadable files without using them
- [ ] T023 [US3] Integrate cache persistence and explicit offline choice in `src/converter/rates_service.py`; save only valid successful online rates and offer, but do not automatically use, the last successful cache after source unavailability
- [ ] T024 [US3] Update `src/converter/gui.py` to show source-unavailable errors, prompt to accept or decline cached rates with their date, and label accepted results `cache from DD.MM.YYYY`

**Checkpoint**: With no network, the app remains usable; cached data is offered only with clear
user consent and is always identified by its actual date.

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Document, exercise, and verify the complete application.

- [ ] T025 Document installation, `python -m converter`, and `python -m pytest` in `README.md`
- [ ] T026 Run `python -m pytest` for `tests/` with network access disabled; confirm every GUI-independent core module has unit tests and fix any failures in the affected `src/converter/` and `tests/` files
- [ ] T027 Validate the runnable online, fallback-date, invalid-input, and offline-cache scenarios from `specs/001-bnm-currency-converter/quickstart.md` against the completed application

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T001 and T002 can proceed in parallel.
- **Foundational (Phase 2)**: Depends on package setup; T003 supplies test fixture data before
  parser and service tests.
- **User Story 4 (Phase 3)**: Depends on setup; establishes safe input handling before the
  conversion form is completed.
- **User Story 1 (Phase 4)**: Depends on User Story 4 for amount validation and form controls.
- **User Story 2 (Phase 5)**: Depends on User Story 1's client/parser/single-date rate service.
- **User Story 3 (Phase 6)**: Depends on User Story 1's rate service and User Story 2's rate
  selection semantics.
- **Polish (Phase 7)**: Depends on all selected stories being complete.

### User Story Dependencies

- **User Story 4 (P1)**: Depends only on Setup and Foundational; independently testable as input
  validation and form-state behavior.
- **User Story 1 (P1)**: Depends on User Story 4's validator and form controls; independently
  proves online conversion using deterministic rates.
- **User Story 2 (P2)**: Depends on User Story 1's BNM client and initial rate service; extends
  date selection without changing conversion behavior.
- **User Story 3 (P2)**: Depends on User Story 1's rate service and User Story 2's date/source
  error distinction; adds persistent cache recovery.

### Parallel Opportunities

- T001 and T002 can run in parallel.
- Within User Story 1, T007, T008, and T009 test files can be authored in parallel. Parser and
  client implementations T011 and T012 can proceed in parallel after their tests are specified;
  T013 follows the parser's `Rate` contract.
- The different pure-module test files `tests/test_parser.py`, `tests/test_bnm_client.py`,
  `tests/test_converter.py`, `tests/test_validation.py`, and `tests/test_cache.py` can be authored
  independently once shared fixture setup is complete.
- User Story 2 tests can be written before its service changes; its service and GUI changes touch
  different files and may proceed in parallel after test expectations are agreed.
- In User Story 3, cache tests T020 and the service test additions T022 touch different files and
  can be authored in parallel after User Story 2.

### Parallel Example: User Story 1

```powershell
# Author independent tests for different modules
# T007: tests/test_parser.py
# T008: tests/test_bnm_client.py
# T009: tests/test_converter.py

# Implement client and parser independently after their test contracts are clear
# T011: src/converter/parser.py
# T012: src/converter/bnm_client.py
```

### Parallel Example: User Story 3

```powershell
# Author cache and service tests in separate files
# T020: tests/test_cache.py
# T021: tests/test_rates_service.py
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2 setup.
2. Complete User Story 4 to ensure invalid amounts cannot reach conversion.
3. Complete User Story 1 for deterministic online conversion, same-currency handling, currency
   selection, BNM provenance, and a runnable GUI.
4. Run the independent tests for both P1 stories and demonstrate the online conversion flow.

### Incremental Delivery

1. Add User Story 2 and verify dated fallback independently.
2. Add User Story 3 and verify persistent cache recovery independently.
3. Complete documentation and run the full offline-safe test suite and quickstart scenarios.

### Completion Criteria

- Every task is completed with its checkbox checked.
- Each GUI-independent core module has a corresponding pytest unit-test module.
- `python -m pytest` succeeds without network access.
- `python -m converter` starts the Tkinter GUI without a console UI.
- Quickstart scenarios distinguish online, fallback-date, and user-accepted cache results.
