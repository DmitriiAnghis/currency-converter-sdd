"""Conversion history: every successful conversion is kept in a JSON file.

The history is shown on the History tab: search, repeat a conversion, delete
selected rows, clear everything and export to CSV (opens in Excel).
"""

from dataclasses import asdict, dataclass
from datetime import datetime
import csv
import json
from pathlib import Path
from typing import Iterable, Optional

from converter.cache import get_default_cache_path
from converter.converter import Conversion

HISTORY_SCHEMA_VERSION = 1
MAX_ENTRIES = 500

CSV_HEADER = ["Time", "Amount", "From", "Result", "To", "Rate date", "Source"]


def get_default_history_path() -> Path:
    """History lives next to the rates cache (same per-user data folder)."""
    return get_default_cache_path().with_name("history.json")


@dataclass(frozen=True)
class HistoryEntry:
    """One row of the history: what was converted, when and with which rate."""
    id: int
    time: str          # "DD.MM.YYYY HH:MM"
    amount: str
    from_code: str
    to_code: str
    result: str
    rate_date: str     # "DD.MM.YYYY"
    source: str        # "BNM" or "cache"

    @property
    def text(self) -> str:
        return f"{self.amount} {self.from_code} = {self.result} {self.to_code}"

    def matches(self, query: str) -> bool:
        """Case-insensitive search by currency code, amount, result or date."""
        query = query.strip().lower()
        if not query:
            return True
        haystack = " ".join((self.time, self.amount, self.from_code, self.to_code,
                             self.result, self.rate_date, self.source)).lower()
        return all(part in haystack for part in query.split())


class ConversionHistory:
    """List of conversions, newest first. With path=None it lives only in memory."""

    def __init__(self, path: Optional[Path] = None, max_entries: int = MAX_ENTRIES) -> None:
        self.path = path
        self.max_entries = max_entries
        self.load_error: Optional[str] = None
        self._entries: list[HistoryEntry] = []
        self._load()

    # --- Storage -------------------------------------------------------------

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema_version") != HISTORY_SCHEMA_VERSION:
                raise ValueError("unsupported schema version")
            self._entries = [HistoryEntry(**item) for item in data["entries"]]
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # A broken file must not stop the program: start with an empty history.
            self._entries = []
            self.load_error = f"History file is damaged and was reset ({exc})."

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {"schema_version": HISTORY_SCHEMA_VERSION,
                   "entries": [asdict(e) for e in self._entries]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- Queries -------------------------------------------------------------

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, entry_id: int) -> Optional[HistoryEntry]:
        return next((e for e in self._entries if e.id == entry_id), None)

    def search(self, query: str) -> list[HistoryEntry]:
        return [e for e in self._entries if e.matches(query)]

    # --- Changes -------------------------------------------------------------

    def add(self, conv: Conversion, now: Optional[datetime] = None) -> HistoryEntry:
        now = now or datetime.now()
        next_id = max((e.id for e in self._entries), default=0) + 1
        entry = HistoryEntry(
            id=next_id,
            time=now.strftime("%d.%m.%Y %H:%M"),
            amount=str(conv.amount),
            from_code=conv.from_code,
            to_code=conv.to_code,
            result=conv.result_formatted,
            rate_date=conv.rate_date.strftime("%d.%m.%Y"),
            source="cache" if conv.source == "cache" else "BNM",
        )
        self._entries.insert(0, entry)
        del self._entries[self.max_entries:]
        self._save()
        return entry

    def delete(self, entry_ids: Iterable[int]) -> int:
        ids = set(entry_ids)
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id not in ids]
        removed = before - len(self._entries)
        if removed:
            self._save()
        return removed

    def clear(self) -> int:
        removed = len(self._entries)
        self._entries = []
        self._save()
        return removed

    # --- Export --------------------------------------------------------------

    @staticmethod
    def export_csv(entries: Iterable[HistoryEntry], path: Path) -> int:
        """Write rows to CSV (";" separator, UTF-8 with BOM, so Excel opens it as is)."""
        rows = list(entries)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(CSV_HEADER)
            for e in rows:
                writer.writerow([e.time, e.amount, e.from_code, e.result, e.to_code,
                                 e.rate_date, e.source])
        return len(rows)


def export_rates_csv(rate_set, path: Path) -> int:
    """Rates tab export: code, name, nominal, MDL rate and rate for one unit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    popular = ["EUR", "USD", "RON", "UAH", "RUB", "GBP"]
    codes = [c for c in popular if c in rate_set.currencies]
    codes += sorted(c for c in rate_set.currencies if c not in popular)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Code", "Currency", "Nominal", "MDL", "1 unit", "Date"])
        for code in codes:
            c = rate_set.currencies[code]
            writer.writerow([c.code, c.name, c.nominal, f"{c.value_mdl:.4f}",
                             f"{c.unit_rate_mdl:.4f}", rate_set.date.strftime("%d.%m.%Y")])
    return len(codes)
