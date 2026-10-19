"""XML parser for official BNM exchange rate responses."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
import xml.etree.ElementTree as ET


class ParserError(Exception):
    """Base exception for rate parsing errors."""
    pass


class EmptyResponse(ParserError):
    """Raised when the XML response is syntactically valid but contains no rates."""
    pass


class InvalidResponse(ParserError):
    """Raised when the XML response is malformed or structurally invalid."""
    pass


@dataclass(frozen=True)
class Currency:
    """Represents one currency and its rate against MDL."""
    code: str
    name: str
    nominal: int
    value_mdl: Decimal

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("Currency code cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Currency name cannot be empty")
        if self.nominal <= 0:
            raise ValueError("Nominal must be a positive integer")
        if self.value_mdl <= 0:
            raise ValueError("Value must be a positive decimal")

    @property
    def unit_rate_mdl(self) -> Decimal:
        """Rate per 1 unit of this currency in MDL: value_mdl / nominal."""
        return self.value_mdl / Decimal(self.nominal)


@dataclass
class RateSet:
    """Represents the complete set of rates for a given date."""
    date: date
    currencies: dict[str, Currency]
    source: str = "bnm"
    is_cached: bool = False
    notice: Optional[str] = None


MDL_CURRENCY = Currency(
    code="MDL",
    name="Moldovan Leu",
    nominal=1,
    value_mdl=Decimal("1"),
)


def parse_bnm_xml(xml_content: str | bytes) -> RateSet:
    """Parse BNM XML content into a RateSet.

    Raises:
        EmptyResponse: If the XML is valid <ValCurs> but contains no <Valute> elements.
        InvalidResponse: If the XML is malformed, has invalid root/fields, duplicate codes,
                         or non-positive values.
    """
    if isinstance(xml_content, str):
        # Strip leading/trailing whitespace
        xml_content = xml_content.strip()

    try:
        root = ET.fromstring(xml_content)
    except (ET.ParseError, ValueError, TypeError) as exc:
        raise InvalidResponse(f"Malformed XML response: {exc}") from exc

    if root.tag != "ValCurs":
        raise InvalidResponse(f"Unexpected root tag '{root.tag}', expected 'ValCurs'")

    date_str = root.attrib.get("Date")
    if not date_str:
        raise InvalidResponse("Missing required 'Date' attribute on ValCurs root")

    try:
        effective_date = datetime.strptime(date_str.strip(), "%d.%m.%Y").date()
    except ValueError as exc:
        raise InvalidResponse(f"Invalid Date attribute format '{date_str}', expected DD.MM.YYYY") from exc

    valute_elements = root.findall("Valute")
    if not valute_elements:
        raise EmptyResponse("Empty ValCurs: response contains no Valute entries")

    currencies: dict[str, Currency] = {}

    for valute in valute_elements:
        char_code_elem = valute.find("CharCode")
        name_elem = valute.find("Name")
        nominal_elem = valute.find("Nominal")
        value_elem = valute.find("Value")

        if (
            char_code_elem is None
            or char_code_elem.text is None
            or name_elem is None
            or name_elem.text is None
            or nominal_elem is None
            or nominal_elem.text is None
            or value_elem is None
            or value_elem.text is None
        ):
            raise InvalidResponse("Valute entry missing required child elements (CharCode, Name, Nominal, Value)")

        code = char_code_elem.text.strip()
        if not code:
            raise InvalidResponse("Valute has empty CharCode")

        if code in currencies:
            raise InvalidResponse(f"Duplicate currency CharCode '{code}' in rate response")

        name = name_elem.text.strip()
        if not name:
            raise InvalidResponse("Valute has empty Name")

        nominal_raw = nominal_elem.text.strip()
        try:
            nominal = int(nominal_raw)
            if nominal <= 0:
                raise ValueError()
        except ValueError as exc:
            raise InvalidResponse(f"Invalid nominal '{nominal_raw}' for currency '{code}', must be positive integer") from exc

        value_raw = value_elem.text.strip().replace(",", ".")
        try:
            value_mdl = Decimal(value_raw)
            if value_mdl <= 0 or not value_mdl.is_finite():
                raise ValueError()
        except (InvalidOperation, ValueError) as exc:
            raise InvalidResponse(f"Invalid value '{value_raw}' for currency '{code}', must be positive decimal") from exc

        currencies[code] = Currency(
            code=code,
            name=name,
            nominal=nominal,
            value_mdl=value_mdl,
        )

    # Ensure MDL base currency is included
    if "MDL" not in currencies:
        currencies["MDL"] = MDL_CURRENCY

    return RateSet(
        date=effective_date,
        currencies=currencies,
        source="bnm",
        is_cached=False,
    )
