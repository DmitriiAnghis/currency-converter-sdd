# User Interface Contract

## Conversion form

- Present a positive amount input, source currency selector, target currency selector, date
  selector defaulting to today, and a Convert button.
- Populate currency choices with MDL and all currencies in the selected rate set.
- Order EUR, USD, RON, UAH, RUB, and GBP first when present; list remaining currencies after
  those, without omitting any source currency.
- Keep Convert disabled until the amount field is non-empty and both currencies are selected.
- Accept either comma or period as the sole decimal separator. Invalid, zero, and negative
  amounts produce an understandable validation message and no conversion result.

## Result display

For a successful conversion, display the entered amount and source code, converted amount and
target code, reverse rate (source units per one target unit), the effective rate date, and
provenance.

- Converted amounts display exactly two decimal places, using half-up rounding.
- Online provenance label: `BNM, official rate for DD.MM.YYYY`.
- Cached provenance label: `cache from DD.MM.YYYY`.
- The displayed date is always the actual date of the rates used.
- When a prior date is selected after no rates were found, show a notice that explicitly names
  the fallback date.

## Errors and offline choice

- A network or server error is shown as a clear source-unavailable message; it is not shown as a
  successful conversion.
- If a validated cached rate set exists, offer the user an explicit choice to use it and show its
  effective date in the offer.
- If the user declines, or no usable cache exists, do not convert and leave the interface usable.
- Malformed source data, invalid cache data, and file errors are reported clearly and do not
  crash the application.
- Error and fallback notices do not conceal the actual rate provenance or date on any displayed
  result.

## Responsiveness and ownership

The interface remains interactive while a rate request is pending. Network work runs outside the
Tk event loop; only the Tk thread creates or updates widgets. All results and failures are
delivered to the user through visible interface state or messages, not a console UI.
