# Feature Specification: BNM Currency Converter

**Feature Branch**: `001-bnm-currency-converter`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "A desktop currency converter with a graphical interface, using the official exchange rates of the National Bank of Moldova (BNM). It supports amount and currency selection, a rate date, conversion results with reverse rates, clear rate-source and date information, recovery through the last successful cached rates when offline, earlier-date lookup when rates are unavailable, input validation, and conversions between any supported currencies. Charts, history, and accounts are out of scope."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convert an Amount (Priority: P1)

A user enters an amount, selects source and target currencies, chooses a rate date, and converts
the amount using official BNM rates. The result includes the converted amount, the reverse rate,
the date of the rates actually used, and whether the rates came from BNM or the local cache.

**Why this priority**: Conversion is the primary purpose of the application.

**Independent Test**: With a known set of official rates available, enter an amount and two
currencies, convert, and verify the displayed result, reverse rate, and provenance.

**Acceptance Scenarios**:

1. **Given** a valid positive amount and two different supported currencies, **When** the user
   converts, **Then** the application displays the converted amount rounded to two decimal places,
   the reverse rate, the rate date, and the official BNM source.
2. **Given** the same currency is selected as source and target, **When** the user converts a
   valid amount, **Then** the result equals the entered amount and the reverse rate is 1.
3. **Given** two non-MDL currencies, **When** the user converts in either direction, **Then** the
   conversion uses the corresponding rates against MDL and accounts for each currency's nominal
   units.
4. **Given** a valid amount and currencies, **When** the user enters the amount using either a
   comma or a period as the decimal separator, **Then** the application accepts it and converts
   the same numeric value.
5. **Given** the conversion form is opened, **When** its initial state is displayed, **Then** the
   rate date is today and available currencies include MDL and every currency in the BNM rates,
   with EUR, USD, RON, UAH, RUB, and GBP listed first when available.
6. **Given** rates are being fetched, **When** the request is delayed, **Then** the user can
   continue editing the form and the window continues repainting without waiting for the request.

---

### User Story 2 - Select a Rate Date (Priority: P2)

A user chooses the date for the rates. If no rates are published for that date, the application
looks back to the most recent available rates within the allowed period and clearly identifies
the actual date used.

**Why this priority**: BNM rates are not available for every calendar day, and users need usable,
accurately dated rates on weekends, holidays, and before new rates are published.

**Independent Test**: Select a date with no published rates followed by a date with available
rates; verify the application chooses the latest available date in the search window and reports
that date in the result and source label.

**Acceptance Scenarios**:

1. **Given** rates are available for the selected date, **When** the user converts, **Then** the
   application uses those rates and identifies the selected date as the rate date.
2. **Given** the selected date has no rates, **When** an earlier date within the ten-day lookback
   has rates, **Then** the application uses the first available rates found while stepping back
   one calendar day at a time and explicitly identifies the actual rate date.
3. **Given** no rates are available within the ten-day lookback, **When** the lookup completes,
   **Then** the application does not convert and tells the user that no rates were found for the
   search period.
4. **Given** the source returns malformed rate data, **When** the user requests a conversion,
   **Then** the application reports that rates could not be read and does not produce a result.

---

### User Story 3 - Convert Without a Network Connection (Priority: P2)

A user can recover gracefully when the BNM source cannot be reached. If previously successful
rates are saved, the application offers the user the choice to use those rates and identifies
their date; otherwise it explains that rates are unavailable.

**Why this priority**: Users need clear, recoverable behavior during connectivity problems rather
than an application failure or an ambiguous result.

**Independent Test**: Make the BNM source unavailable, then test both with saved successful rates
and without any saved rates; verify the corresponding offer or clear unavailable message.

**Acceptance Scenarios**:

1. **Given** the BNM source cannot be reached and a previously successful response is saved,
   **When** the user requests rates, **Then** the application clearly reports the connection
   problem and offers to use the saved rates, showing their date before conversion.
2. **Given** the BNM source cannot be reached and no successful response is saved, **When** the
   user requests rates, **Then** the application remains usable, reports that rates are
   unavailable, and does not convert.
3. **Given** the user accepts use of saved rates, **When** conversion completes, **Then** the
   result identifies the date of those cached rates and identifies the data as cached.
4. **Given** saved rates have been used successfully, **When** the application is closed and
   reopened, **Then** those rates remain available for an offline-use offer.

---

### User Story 4 - Correct Invalid Amounts (Priority: P1)

A user receives an understandable validation message instead of a conversion when the amount is
empty, zero, negative, or not a number.

**Why this priority**: A result must never imply that an invalid amount was successfully converted.

**Independent Test**: Enter each invalid amount in turn and attempt conversion; verify no result is
produced and an actionable validation message is shown.

**Acceptance Scenarios**:

1. **Given** the amount is empty or either currency is not selected, **When** the form is shown,
   **Then** the Convert button is disabled.
2. **Given** the amount is zero, negative, or contains letters or other invalid characters,
   **When** the user attempts conversion, **Then** conversion does not occur and a clear
   validation message is shown.
3. **Given** the amount is invalid, **When** the user corrects it to a positive number, **Then**
   the validation message clears and conversion can proceed.

### Edge Cases

- Rates are unavailable for the selected date and for every date in the ten-day lookback.
- The source cannot be reached while looking for a date with published rates.
- The source response is malformed or does not contain usable rates.
- The saved rate data is missing, unreadable, or invalid.
- The saved rate date is different from the user's selected date; the actual cached rate date is
  shown and is not presented as the selected date.
- The amount contains both comma and period separators, multiple separators, whitespace, or
  otherwise invalid characters.
- The source currency and target currency are identical.
- A currency's nominal amount is greater than one; rates and cross conversions must account for
  that nominal amount.
- A user requests rates before BNM has published rates for the selected working day.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST provide a graphical desktop interface for currency conversion.
- **FR-002**: The application MUST obtain official exchange rates from the National Bank of
  Moldova (BNM).
- **FR-003**: The application MUST provide an amount field, source- and target-currency selectors,
  a rate-date selector defaulting to today, and a Convert button.
- **FR-004**: The currency selectors MUST include MDL and all currencies present in the retrieved
  BNM rate data. They MUST present EUR, USD, RON, UAH, RUB, and GBP before other currencies when
  those currencies are available.
- **FR-005**: The Convert button MUST remain disabled until the amount is non-empty and both
  currencies are selected.
- **FR-006**: The application MUST reject empty, zero, negative, and non-numeric amounts and MUST
  show a clear validation message without producing a conversion result.
- **FR-007**: The application MUST accept either a comma or a period as the decimal separator for
  an otherwise valid positive amount.
- **FR-008**: The application MUST use MDL as the base currency at rate 1. For each other
  currency, it MUST calculate the per-unit MDL rate by dividing the published MDL value by its
  nominal quantity. It MUST convert an amount by applying the source currency's per-unit MDL
  rate and dividing by the target currency's per-unit MDL rate, including cross conversions
  between two non-MDL currencies in both directions.
- **FR-009**: Selecting the same currency for both sides MUST produce the entered amount as the
  result and a reverse rate of 1, without an error.
- **FR-010**: The application MUST display the converted amount to two decimal places and show the
  reverse rate, expressed as source-currency units per one target-currency unit, formatted to
  four decimal places using half-up rounding. The unrounded reverse rate MUST be retained
  internally. Exchange rates MUST retain the precision published by BNM.
- **FR-011**: The application MUST identify the rate date actually used and its provenance. For
  online rates, it MUST display "BNM, official rate for DD.MM.YYYY"; for saved rates, it MUST
  display "cache from DD.MM.YYYY", substituting the actual rate date in each label.
- **FR-012**: When BNM returns no rates for the selected date, the application MUST check previous
  calendar dates one day at a time, up to ten days earlier, and use the first available rates.
- **FR-013**: When an earlier date's rates are used, the application MUST explicitly tell the user
  the actual rate date. If no rates are found in the lookback period, it MUST report that no
  conversion can be made.
- **FR-014**: When the BNM source cannot be reached, the application MUST remain usable and show a
  clear connection error. If saved successful rates exist, it MUST offer the user the choice to
  use them and MUST show their date.
- **FR-015**: When the user chooses to use saved rates, the application MUST identify their
  cached date and provenance in the result.
- **FR-016**: The application MUST save the last successful BNM rate response locally in the
  user's data area and retain it across application restarts.
- **FR-017**: Network, data-reading, and saved-file errors MUST be communicated clearly and MUST
  NOT crash the application.
- **FR-018**: The application MUST exclude charts, conversion history, and user accounts from
  this feature.

### Key Entities *(include if feature involves data)*

- **Currency**: A supported currency, identified by its code and name, with its nominal quantity
  and BNM-published value in MDL; MDL has a base rate of 1.
- **Rate set**: A dated collection of official currency rates, including the date the rates
  apply and whether the data currently used came from BNM or the saved cache.
- **Conversion**: A user's positive input amount, selected source and target currencies, rate
  date, converted amount, and reverse rate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance tests, 100% of valid same-currency, MDL-to-currency,
  currency-to-MDL, and non-MDL cross-currency examples produce the expected result using the
  published nominal quantities and rates.
- **SC-002**: In acceptance tests, 100% of empty, zero, negative, and non-numeric amounts produce
  no conversion and a clear validation message; valid comma- and period-decimal inputs are both
  accepted.
- **SC-003**: In acceptance tests, every successful result identifies the actual rate date and
  whether the rates came from BNM or the cache.
- **SC-004**: For any test date with rates available within the lookback period, the application
  selects the first available rate date encountered while checking backward and checks no date
  more than ten days earlier than the selected date.
- **SC-005**: During a simulated 10-second rate request, the application continues repainting and
  accepts amount-field edits within 1 second without waiting for the request to finish. In
  offline acceptance tests, it offers saved rates when present and reports unavailable rates
  without a conversion when no saved rates exist.
- **SC-006**: At least 9 out of 10 first-time users in a usability test can identify where to
  enter an amount, choose currencies and a date, and complete a valid conversion without
  assistance.

## Assumptions

- The date shown in the result and source label is always the date of the rates actually used,
  which may differ from the requested date.
- The ten-day lookback means checking the selected date and then dates up to ten calendar days
  earlier.
- If the network fails during a date lookup, the application reports the connection error and
  offers any saved successful response; it does not imply that the selected date was searched
  successfully.
- Saved data represents the last successful source response. If the user accepts it for an
  offline conversion, the application clearly labels it as cached and uses its own saved date.
- Amounts are rounded to two decimal places using the conventional half-up rule; source rate
  precision is not rounded before conversion.
- A valid amount must be greater than zero. Commas and periods are accepted individually as
  decimal separators; grouping separators are not required.
- All currencies returned by BNM are available to select, while the listed popular currencies
  appear first whenever present.
- Charts, history, and accounts are outside this feature's scope.
