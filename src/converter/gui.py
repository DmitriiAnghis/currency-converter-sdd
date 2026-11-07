"""Graphical user interface for BNM Currency Converter using Tkinter.

One window with tabs; messages appear as banners, never as pop-up windows.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

# Ensure Tcl/Tk can locate their standard libraries if not set
_tcl_dir = os.path.join(sys.prefix, "tcl", "tcl8.6")
_tk_dir = os.path.join(sys.prefix, "tcl", "tk8.6")
if "TCL_LIBRARY" not in os.environ and os.path.exists(_tcl_dir):
    os.environ["TCL_LIBRARY"] = _tcl_dir
if "TK_LIBRARY" not in os.environ and os.path.exists(_tk_dir):
    os.environ["TK_LIBRARY"] = _tk_dir

from converter.bnm_client import SourceUnavailableError
from converter.converter import Conversion, convert
from converter.history import ConversionHistory, HistoryEntry, export_rates_csv
from converter.parser import RateSet
from converter.rates_service import (
    InvalidDataError,
    NoRatesFoundError,
    RatesResult,
    RatesService,
)
from converter.validation import ValidationError, parse_amount


POPULAR_CURRENCIES = ["EUR", "USD", "RON", "UAH", "RUB", "GBP"]


def order_currencies(currency_codes: list[str]) -> list[str]:
    """Order currencies with EUR, USD, RON, UAH, RUB, GBP first, then others alphabetically."""
    popular = [c for c in POPULAR_CURRENCIES if c in currency_codes]
    others = sorted([c for c in currency_codes if c not in POPULAR_CURRENCIES])
    return popular + others




# --- Design tokens: every colour and the font are defined once here ----------

FONT = "Segoe UI"
COLORS = {
    "bg": "#F4F6FB",
    "card": "#FFFFFF",
    "border": "#E3E7F0",
    "header": "#1E2A4A",
    "header_text": "#FFFFFF",
    "header_muted": "#AEB8D6",
    "text": "#1F2430",
    "muted": "#6B7280",
    "accent": "#3B5BDB",
    "accent_hover": "#2F4BC0",
    "accent_disabled": "#B9C4EE",
    "badge_bg": "#EDF1FF",
    "secondary_hover": "#DCE3FF",
    "warn_bg": "#FFF4E5",
    "warn_text": "#9A5B00",
    "error": "#C92A2A",
    "error_bg": "#FFF0F0",
    "ok_bg": "#EBFBEE",
    "ok_text": "#2B8A3E",
    "row_alt": "#F8F9FD",
}

BANNER_KINDS = {
    "ok": ("ok_bg", "ok_text"),
    "warn": ("warn_bg", "warn_text"),
    "error": ("error_bg", "error"),
}


def _setup_styles(root: tk.Misc) -> None:
    """ttk theme: accent/secondary buttons, inputs, tabs and tables."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    c = COLORS
    style.configure(".", font=(FONT, 10), background=c["card"], foreground=c["text"])
    style.configure("Card.TFrame", background=c["card"])
    style.configure("Bg.TFrame", background=c["bg"])
    style.configure("TEntry", padding=6, fieldbackground=c["card"], bordercolor=c["border"],
                    lightcolor=c["border"], darkcolor=c["border"])
    style.map("TEntry", bordercolor=[("focus", c["accent"])],
              lightcolor=[("focus", c["accent"])])
    style.configure("TCombobox", padding=6, fieldbackground=c["card"],
                    bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                    arrowcolor=c["accent"], background=c["card"])
    style.map("TCombobox", bordercolor=[("focus", c["accent"])],
              fieldbackground=[("readonly", c["card"])],
              selectbackground=[("readonly", c["card"])],
              selectforeground=[("readonly", c["text"])])
    style.configure("Accent.TButton", font=(FONT, 11, "bold"), padding=(18, 10),
                    background=c["accent"], foreground="#FFFFFF", borderwidth=0,
                    focuscolor=c["accent"])
    style.map("Accent.TButton",
              background=[("disabled", c["accent_disabled"]), ("active", c["accent_hover"])],
              foreground=[("disabled", "#FFFFFF")])
    style.configure("Secondary.TButton", font=(FONT, 10, "bold"), padding=(14, 8),
                    background=c["badge_bg"], foreground=c["accent"], borderwidth=0,
                    focuscolor=c["badge_bg"])
    style.map("Secondary.TButton",
              background=[("disabled", c["bg"]), ("active", c["secondary_hover"])],
              foreground=[("disabled", c["accent_disabled"])])
    # Compact buttons for the row under the history table.
    style.configure("SmallAccent.TButton", font=(FONT, 10, "bold"), padding=(12, 8),
                    background=c["accent"], foreground="#FFFFFF", borderwidth=0,
                    focuscolor=c["accent"])
    style.map("SmallAccent.TButton",
              background=[("disabled", c["accent_disabled"]), ("active", c["accent_hover"])],
              foreground=[("disabled", "#FFFFFF")])
    style.configure("Small.TButton", font=(FONT, 10, "bold"), padding=(10, 8),
                    background=c["badge_bg"], foreground=c["accent"], borderwidth=0,
                    focuscolor=c["badge_bg"])
    style.map("Small.TButton",
              background=[("disabled", c["bg"]), ("active", c["secondary_hover"])],
              foreground=[("disabled", c["accent_disabled"])])
    style.configure("Swap.TButton", font=(FONT, 13, "bold"), padding=(10, 4),
                    background=c["badge_bg"], foreground=c["accent"], borderwidth=0,
                    focuscolor=c["badge_bg"])
    style.map("Swap.TButton", background=[("active", c["secondary_hover"])])
    # Tabs: the selected tab is filled with the accent colour, no focus dashes.
    style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(20, 12, 20, 0),
                    bordercolor=c["bg"], lightcolor=c["bg"], darkcolor=c["bg"])
    style.configure("TNotebook.Tab", font=(FONT, 10, "bold"), padding=(18, 8),
                    background=c["bg"], foreground=c["muted"], borderwidth=0,
                    bordercolor=c["bg"], lightcolor=c["bg"], darkcolor=c["bg"],
                    focuscolor=c["bg"])
    style.map("TNotebook.Tab",
              background=[("selected", c["accent"]), ("active", c["badge_bg"])],
              foreground=[("selected", "#FFFFFF"), ("active", c["accent"])],
              bordercolor=[("selected", c["accent"])], lightcolor=[("selected", c["accent"])],
              expand=[("selected", (0, 0, 0, 0))])
    style.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
    # Tables
    style.configure("Treeview", font=(FONT, 10), rowheight=28, background=c["card"],
                    fieldbackground=c["card"], bordercolor=c["border"], borderwidth=0)
    style.map("Treeview", background=[("selected", c["accent"])],
              foreground=[("selected", "#FFFFFF")])
    style.configure("Treeview.Heading", font=(FONT, 9, "bold"), background=c["bg"],
                    foreground=c["muted"], borderwidth=0, padding=(8, 6))
    style.map("Treeview.Heading", background=[("active", c["border"])])
    style.configure("Vertical.TScrollbar", background=c["border"], troughcolor=c["card"],
                    bordercolor=c["card"], lightcolor=c["border"], darkcolor=c["border"],
                    arrowcolor=c["muted"], gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", c["accent_disabled"])])
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])


def _label(parent: tk.Misc, text: str = "", fg: str = "text", bg: str = "card",
           size: int = 10, bold: bool = False, **kw: Any) -> tk.Label:
    return tk.Label(parent, text=text, fg=COLORS[fg], bg=COLORS[bg],
                    font=(FONT, size, "bold" if bold else "normal"), **kw)


def _card(parent: tk.Misc, padding: int = 18) -> tuple[tk.Frame, ttk.Frame]:
    """White card with a 1 px border. Returns (outer, inner); pack/grid the outer."""
    outer = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=padding)
    inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


def _field_caption(parent: tk.Misc, text: str) -> tk.Label:
    return _label(parent, text.upper(), "muted", size=9, bold=True)


def _format_rate(value: Decimal) -> str:
    return f"{value:.4f}"


class ConverterApp:
    """Desktop GUI application for currency conversion.

    One window with three tabs (Converter, Rates, History). Messages are shown as a
    banner under the header and as red text under the form, never as pop-up windows.
    """

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        rates_service: Optional[RatesService] = None,
        history: Optional[ConversionHistory] = None,
        export_dir: Optional[Path] = None,
    ) -> None:
        self.root = root if root is not None else tk.Tk()
        self.root.title("BNM Currency Converter")
        self.root.geometry("600x820")
        self.root.minsize(540, 780)

        self.rates_service = rates_service
        # Without a file the history lives in memory only (tests, demo).
        self.history = history if history is not None else ConversionHistory(None)
        self.export_dir = export_dir if export_dir is not None else default_export_dir()

        # State variables
        self.amount_var = tk.StringVar()
        self.from_currency_var = tk.StringVar(value="")
        self.to_currency_var = tk.StringVar(value="")
        self.date_var = tk.StringVar(value=date.today().strftime("%d.%m.%Y"))

        self.status_message_var = tk.StringVar()
        self.validation_error_var = tk.StringVar()
        self.result_main_var = tk.StringVar()
        self.result_reverse_var = tk.StringVar()
        self.result_provenance_var = tk.StringVar()
        self.result_notice_var = tk.StringVar()
        self.header_stats_var = tk.StringVar(value="Official exchange rates from the National Bank of Moldova")
        self.rates_search_var = tk.StringVar()
        self.rates_caption_var = tk.StringVar()
        self.history_search_var = tk.StringVar()
        self.history_caption_var = tk.StringVar()

        initial_defaults = ["EUR", "USD", "RON", "UAH", "RUB", "GBP", "MDL"]
        self.available_currencies: list[str] = order_currencies(initial_defaults)
        self.current_rates_result: Optional[RatesResult] = None
        self._cached_rate_set_to_offer: Optional[RateSet] = None
        self._busy = False
        self._banner_after: Optional[str] = None

        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._update_convert_button_state()
        self._refresh_result_view()
        self._schedule_queue_processing()

        if self.history.load_error:
            self.notify(self.history.load_error, "warn")
        if self.rates_service is not None:
            self._load_initial_rates()

    def _schedule_queue_processing(self) -> None:
        self._process_queue()

    def _process_queue(self) -> None:
        while not self._queue.empty():
            try:
                fn = self._queue.get_nowait()
                fn()
            except queue.Empty:
                break
            except Exception:
                pass
        try:
            self.root.after(50, self._process_queue)
        except Exception:
            pass

    # --- Layout -------------------------------------------------------------

    def _configure_styles(self) -> None:
        _setup_styles(self.root)
        self.root.configure(bg=COLORS["bg"])

    def _build_ui(self) -> None:
        c = COLORS
        # Dark header: title and a stats line with the rates currently loaded.
        self.header = tk.Frame(self.root, bg=c["header"], padx=24, pady=14)
        self.header.pack(fill=tk.X)
        _label(self.header, "BNM Currency Converter", "header_text", "header", 15,
               bold=True).pack(anchor=tk.W)
        self.header_stats = tk.Label(self.header, textvariable=self.header_stats_var,
                                     fg=c["header_muted"], bg=c["header"], font=(FONT, 9))
        self.header_stats.pack(anchor=tk.W, pady=(2, 0))

        self._build_banner()
        self._build_cache_offer()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.enable_traversal()

        converter_tab = ttk.Frame(self.notebook, style="Bg.TFrame", padding=(20, 16, 20, 20))
        rates_tab = ttk.Frame(self.notebook, style="Bg.TFrame", padding=(20, 16, 20, 20))
        self.history_tab = ttk.Frame(self.notebook, style="Bg.TFrame", padding=(20, 16, 20, 20))
        self.notebook.add(converter_tab, text="Converter")
        self.notebook.add(rates_tab, text="Rates")
        self.notebook.add(self.history_tab, text="History")

        self._build_form(converter_tab)
        self._build_result(converter_tab)
        self._build_rates_tab(rates_tab)
        self._build_history_tab(self.history_tab)

    def _build_banner(self) -> None:
        """Notification strip under the header (instead of message boxes)."""
        c = COLORS
        self.banner = tk.Frame(self.root, bg=c["ok_bg"], padx=20, pady=4)
        self.banner_label = tk.Label(self.banner, bg=c["ok_bg"], fg=c["ok_text"],
                                     font=(FONT, 10, "bold"), anchor="w", justify="left",
                                     wraplength=440)
        self.banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
        self.banner_close = tk.Button(self.banner, text="✕", bd=0, relief="flat",
                                      bg=c["ok_bg"], activebackground=c["ok_bg"],
                                      fg=c["ok_text"], font=(FONT, 10, "bold"),
                                      cursor="hand2", command=self.hide_banner)
        self.banner_action = ttk.Button(self.banner, style="Secondary.TButton")

    def _build_cache_offer(self) -> None:
        """Warn strip offering the saved (cached) rates when BNM is unreachable."""
        c = COLORS
        self.cache_prompt_frame = tk.Frame(self.root, bg=c["warn_bg"], padx=20, pady=8)
        self.cache_prompt_label = tk.Label(
            self.cache_prompt_frame, text="", bg=c["warn_bg"], fg=c["warn_text"],
            font=(FONT, 10, "bold"), justify="left", anchor="w", wraplength=540,
        )
        self.cache_prompt_label.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))
        cache_buttons_row = tk.Frame(self.cache_prompt_frame, bg=c["warn_bg"])
        cache_buttons_row.pack(fill=tk.X)
        self.cache_accept_btn = ttk.Button(
            cache_buttons_row,
            text="Use saved rates",
            style="Accent.TButton",
            command=self._on_accept_cache,
        )
        self.cache_accept_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.cache_decline_btn = ttk.Button(
            cache_buttons_row,
            text="Decline",
            style="Secondary.TButton",
            command=self._on_decline_cache,
        )
        self.cache_decline_btn.pack(side=tk.LEFT)

    def _build_form(self, parent: ttk.Frame) -> None:
        outer, form = _card(parent, padding=16)
        outer.pack(fill=tk.X, pady=(0, 12))
        form.columnconfigure(0, weight=1)
        form.columnconfigure(2, weight=1)

        _field_caption(form, "Amount").grid(row=0, column=0, columnspan=3, sticky="w")
        self.amount_entry = ttk.Entry(form, textvariable=self.amount_var, font=(FONT, 14))
        self.amount_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        _label(form, "Positive number, comma or dot as decimal separator: 100 or 12,50",
               "muted", size=9).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        _field_caption(form, "From").grid(row=3, column=0, sticky="w")
        _field_caption(form, "To").grid(row=3, column=2, sticky="w")
        self.from_combo = ttk.Combobox(
            form,
            textvariable=self.from_currency_var,
            values=self.available_currencies,
            state="readonly",
            font=(FONT, 11),
        )
        self.from_combo.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        self.swap_button = ttk.Button(form, text="⇄", width=3, style="Swap.TButton",
                                      command=self._swap_currencies)
        self.swap_button.grid(row=4, column=1, padx=8, pady=(4, 0))
        self.to_combo = ttk.Combobox(
            form,
            textvariable=self.to_currency_var,
            values=self.available_currencies,
            state="readonly",
            font=(FONT, 11),
        )
        self.to_combo.grid(row=4, column=2, sticky="ew", pady=(4, 0))
        self.from_name_label = _label(form, "", "muted", size=9)
        self.from_name_label.grid(row=5, column=0, sticky="w", pady=(2, 12))
        self.to_name_label = _label(form, "", "muted", size=9)
        self.to_name_label.grid(row=5, column=2, sticky="w", pady=(2, 12))

        _field_caption(form, "Rate date (DD.MM.YYYY)").grid(row=6, column=0, columnspan=3,
                                                             sticky="w")
        date_row = ttk.Frame(form, style="Card.TFrame")
        date_row.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        self.date_entry = ttk.Entry(date_row, textvariable=self.date_var, font=(FONT, 11))
        self.date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(date_row, text="◀ Day", style="Secondary.TButton",
                   command=lambda: self._shift_date(-1)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(date_row, text="Today", style="Secondary.TButton",
                   command=self._set_today_date).pack(side=tk.LEFT, padx=(8, 0))
        _label(form, "No rates for that day? The last rate within 10 days is used.",
               "muted", size=9).grid(row=8, column=0, columnspan=3, sticky="w")

        # Errors are shown in red right under the form, not in a pop-up.
        self.validation_label = tk.Label(
            form, textvariable=self.validation_error_var, fg=COLORS["error"],
            bg=COLORS["card"], font=(FONT, 9, "bold"), justify="left", anchor="w",
            wraplength=500,
        )
        self.validation_label.grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.status_label = tk.Label(
            form, textvariable=self.status_message_var, fg=COLORS["accent"],
            bg=COLORS["card"], font=(FONT, 9, "bold"), anchor="w",
        )
        self.status_label.grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._refresh_messages()

        self.convert_button = ttk.Button(
            form,
            text="Convert",
            style="Accent.TButton",
            command=self._on_convert_clicked,
        )
        self.convert_button.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _build_result(self, parent: ttk.Frame) -> None:
        c = COLORS
        self.result_outer, self.result_card = _card(parent, padding=16)
        self.result_outer.pack(fill=tk.BOTH, expand=True)

        # Empty state: big badge, title and one line on what to do.
        self.empty_state = ttk.Frame(self.result_card, style="Card.TFrame")
        _label(self.empty_state, " MDL ", "accent", "badge_bg", 14, bold=True,
               padx=10, pady=4).pack(pady=(4, 8))
        _label(self.empty_state, "No conversion yet", size=12, bold=True).pack()
        _label(self.empty_state, "Enter an amount, pick two currencies and press Convert (Enter).",
               "muted", size=9).pack(pady=(4, 0))

        # Result view
        self.result_view = ttk.Frame(self.result_card, style="Card.TFrame")
        top = ttk.Frame(self.result_view, style="Card.TFrame")
        top.pack(fill=tk.X, pady=(0, 8))
        _label(top, "RESULT", "muted", size=9, bold=True).pack(side=tk.LEFT)
        self.result_route_badge = _label(top, "", "accent", "badge_bg", 9, bold=True,
                                         padx=8, pady=2)
        self.result_route_badge.pack(side=tk.LEFT, padx=(8, 0))
        self.copy_button = ttk.Button(top, text="Copy", style="Secondary.TButton",
                                      command=self._copy_result)
        self.copy_button.pack(side=tk.RIGHT)
        self.result_main_lbl = tk.Label(
            self.result_view, textvariable=self.result_main_var, fg=c["text"], bg=c["card"],
            font=(FONT, 18, "bold"), justify="left", anchor="w", wraplength=520,
        )
        self.result_main_lbl.pack(anchor=tk.W, fill=tk.X)
        self.result_reverse_lbl = tk.Label(
            self.result_view, textvariable=self.result_reverse_var, fg=c["muted"], bg=c["card"],
            font=(FONT, 10), anchor="w",
        )
        self.result_reverse_lbl.pack(anchor=tk.W, pady=(2, 10))
        self.result_provenance_lbl = tk.Label(
            self.result_view, textvariable=self.result_provenance_var, fg=c["ok_text"],
            bg=c["ok_bg"], font=(FONT, 9, "bold"), padx=10, pady=4,
        )
        self.result_provenance_lbl.pack(anchor=tk.W)
        self.result_notice_lbl = tk.Label(
            self.result_view, textvariable=self.result_notice_var, fg=c["warn_text"],
            bg=c["warn_bg"], font=(FONT, 9, "bold"), padx=10, pady=6, justify="left",
            anchor="w", wraplength=500,
        )

    def _build_rates_tab(self, parent: ttk.Frame) -> None:
        outer, card = _card(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill=tk.X, pady=(0, 4))
        _label(top, "Official rates", size=12, bold=True).pack(side=tk.LEFT)
        self.rates_count_badge = _label(top, "0", "accent", "badge_bg", 9, bold=True,
                                        padx=8, pady=2)
        self.rates_count_badge.pack(side=tk.LEFT, padx=(8, 0))
        self.load_rates_button = ttk.Button(top, text="Load for date", style="Secondary.TButton",
                                            command=self._on_load_rates_clicked)
        self.load_rates_button.pack(side=tk.RIGHT)
        self.export_rates_button = ttk.Button(top, text="Export CSV", style="Secondary.TButton",
                                              command=self.export_rates_csv)
        self.export_rates_button.pack(side=tk.RIGHT, padx=(0, 8))
        tk.Label(card, textvariable=self.rates_caption_var, fg=COLORS["muted"],
                 bg=COLORS["card"], font=(FONT, 9), anchor="w").pack(fill=tk.X, pady=(0, 10))

        _field_caption(card, "Search").pack(anchor=tk.W)
        ttk.Entry(card, textvariable=self.rates_search_var).pack(fill=tk.X, pady=(4, 12))

        table = ttk.Frame(card, style="Card.TFrame")
        table.pack(fill=tk.BOTH, expand=True)
        columns = ("Code", "Currency", "Nominal", "MDL", "1 unit")
        widths = (60, 190, 70, 90, 90)
        self.rates_tree = ttk.Treeview(table, columns=columns, show="headings",
                                       selectmode="browse")
        for column, width in zip(columns, widths):
            anchor = "w" if column in ("Code", "Currency") else "e"
            self.rates_tree.heading(column, text=column, anchor=anchor)
            self.rates_tree.column(column, width=width, anchor=anchor,
                                   stretch=column == "Currency")
        self.rates_tree.tag_configure("alt", background=COLORS["row_alt"])
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.rates_tree.yview)
        self.rates_tree.configure(yscrollcommand=scroll.set)
        self.rates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        _label(card, "Double-click a row to convert from that currency.", "muted",
               size=9).pack(anchor=tk.W, pady=(8, 0))
        self._fill_rates_table()

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        outer, card = _card(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill=tk.X, pady=(0, 4))
        _label(top, "Conversion history", size=12, bold=True).pack(side=tk.LEFT)
        self.history_count_badge = _label(top, "0", "accent", "badge_bg", 9, bold=True,
                                          padx=8, pady=2)
        self.history_count_badge.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(card, textvariable=self.history_caption_var, fg=COLORS["muted"],
                 bg=COLORS["card"], font=(FONT, 9), anchor="w").pack(fill=tk.X, pady=(0, 10))

        _field_caption(card, "Search (currency, amount, date)").pack(anchor=tk.W)
        ttk.Entry(card, textvariable=self.history_search_var).pack(fill=tk.X, pady=(4, 12))

        table = ttk.Frame(card, style="Card.TFrame")
        table.pack(fill=tk.BOTH, expand=True)
        columns = ("Time", "Conversion", "Rate date", "Source")
        widths = (126, 210, 84, 66)
        self.history_tree = ttk.Treeview(table, columns=columns, show="headings",
                                         selectmode="extended")
        for column, width in zip(columns, widths):
            self.history_tree.heading(column, text=column, anchor="w")
            self.history_tree.column(column, width=width, anchor="w",
                                     stretch=column == "Conversion",
                                     minwidth=50)
        self.history_tree.tag_configure("alt", background=COLORS["row_alt"])
        self.history_tree.tag_configure("cache", foreground=COLORS["warn_text"])
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scroll.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.pack(fill=tk.X, pady=(10, 0))
        self.history_repeat_button = ttk.Button(buttons, text="Repeat", style="SmallAccent.TButton",
                                                command=self.repeat_selected)
        self.history_repeat_button.pack(side=tk.LEFT)
        self.history_delete_button = ttk.Button(buttons, text="Delete", style="Small.TButton",
                                                command=self.delete_selected)
        self.history_delete_button.pack(side=tk.LEFT, padx=(8, 0))
        self.history_clear_button = ttk.Button(buttons, text="Clear all",
                                               style="Small.TButton",
                                               command=self.ask_clear_history)
        self.history_clear_button.pack(side=tk.LEFT, padx=(8, 0))
        self.history_export_button = ttk.Button(buttons, text="Export CSV",
                                                style="Small.TButton",
                                                command=self.export_history_csv)
        self.history_export_button.pack(side=tk.RIGHT)
        _label(card, "Double-click or Enter repeats a conversion, Delete removes selected rows.",
               "muted", size=9).pack(anchor=tk.W, pady=(8, 0))
        self._fill_history_table()

    def _bind_events(self) -> None:
        self.amount_var.trace_add("write", lambda *_: self._on_field_changed())
        self.from_currency_var.trace_add("write", lambda *_: self._on_field_changed())
        self.to_currency_var.trace_add("write", lambda *_: self._on_field_changed())
        self.result_main_var.trace_add("write", lambda *_: self._refresh_result_view())
        self.result_notice_var.trace_add("write", lambda *_: self._refresh_result_view())
        self.result_provenance_var.trace_add("write", lambda *_: self._refresh_result_view())
        self.validation_error_var.trace_add("write", lambda *_: self._refresh_messages())
        self.status_message_var.trace_add("write", lambda *_: self._refresh_messages())
        self.rates_search_var.trace_add("write", lambda *_: self._fill_rates_table())
        self.rates_tree.bind("<Double-1>", self._on_rate_row_activated)
        self.rates_tree.bind("<Return>", self._on_rate_row_activated)
        self.history_search_var.trace_add("write", lambda *_: self._fill_history_table())
        self.history_tree.bind("<Double-1>", lambda _e: self.repeat_selected())
        self.history_tree.bind("<Return>", lambda _e: self.repeat_selected())
        self.history_tree.bind("<Delete>", lambda _e: self.delete_selected())
        self.history_tree.bind("<<TreeviewSelect>>", lambda _e: self._update_history_buttons())
        for widget in (self.amount_entry, self.date_entry, self.from_combo, self.to_combo):
            widget.bind("<Return>", self._on_enter_pressed)
        self.root.bind("<Escape>", lambda _e: self._clear_form_result())

    # --- Small helpers ---------------------------------------------------------

    def notify(self, text: str, kind: str = "ok",
               action: Optional[Callable[[], None]] = None, action_text: str = "Retry") -> None:
        """Show a banner under the header. ok hides itself after 4 s."""
        bg, fg = (COLORS[k] for k in BANNER_KINDS[kind])
        for widget in (self.banner, self.banner_label, self.banner_close):
            widget.configure(bg=bg)
        self.banner_close.configure(fg=fg, activebackground=bg)
        self.banner_label.configure(text=text, fg=fg)
        self.banner_action.pack_forget()
        self.banner_close.pack_forget()
        if action is not None:
            self.banner_action.configure(text=action_text,
                                         command=lambda: (self.hide_banner(), action()))
            self.banner_action.pack(side=tk.LEFT, padx=(8, 8), pady=4)
        self.banner_close.pack(side=tk.RIGHT)
        self.banner.pack(fill=tk.X, after=self.header)
        if self._banner_after:
            self.root.after_cancel(self._banner_after)
            self._banner_after = None
        if kind == "ok":
            self._banner_after = self.root.after(4000, self.hide_banner)

    def hide_banner(self) -> None:
        self._banner_after = None
        self.banner.pack_forget()

    def _refresh_result_view(self) -> None:
        """Show the empty state until there is a result; hide empty badges."""
        if self.result_main_var.get():
            self.empty_state.pack_forget()
            self.result_view.pack(fill=tk.BOTH, expand=True)
        else:
            self.result_view.pack_forget()
            self.empty_state.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        is_cache = self.result_provenance_var.get().startswith("cache")
        kind = "warn" if is_cache else "ok"
        bg, fg = (COLORS[k] for k in BANNER_KINDS[kind])
        self.result_provenance_lbl.configure(bg=bg, fg=fg)
        if self.result_notice_var.get():
            self.result_notice_lbl.pack(anchor=tk.W, fill=tk.X, pady=(10, 0))
        else:
            self.result_notice_lbl.pack_forget()

    def _refresh_messages(self) -> None:
        """Error and status lines take no space while they are empty."""
        for var, lbl in ((self.validation_error_var, self.validation_label),
                         (self.status_message_var, self.status_label)):
            if var.get():
                lbl.grid()
            else:
                lbl.grid_remove()

    def _update_currency_names(self) -> None:
        rates = self.current_rates_result.rates.currencies if self.current_rates_result else {}
        for code_var, lbl in ((self.from_currency_var, self.from_name_label),
                              (self.to_currency_var, self.to_name_label)):
            currency = rates.get(code_var.get())
            lbl.configure(text=currency.name if currency is not None else "")

    def _update_header_stats(self) -> None:
        result = self.current_rates_result
        if result is None:
            return
        count = len(result.rates.currencies)
        self.header_stats_var.set(f"Rates: {result.provenance_label}  ·  {count} currencies")

    def _fill_rates_table(self) -> None:
        tree = self.rates_tree
        tree.delete(*tree.get_children())
        result = self.current_rates_result
        if result is None:
            self.rates_caption_var.set("Rates are not loaded yet. Press “Load for date”.")
            self.rates_count_badge.configure(text="0")
            return
        query = self.rates_search_var.get().strip().lower()
        currencies = result.rates.currencies
        shown = 0
        for code in order_currencies(list(currencies)):
            currency = currencies[code]
            if query and query not in code.lower() and query not in currency.name.lower():
                continue
            tree.insert("", tk.END, iid=code, tags=("alt",) if shown % 2 else (), values=(
                code, currency.name, currency.nominal, _format_rate(currency.value_mdl),
                _format_rate(currency.unit_rate_mdl)))
            shown += 1
        self.rates_count_badge.configure(text=str(shown))
        self.rates_caption_var.set(result.provenance_label)

    def _on_rate_row_activated(self, _event: Any = None) -> None:
        selection = self.rates_tree.selection()
        if not selection:
            return
        code = selection[0]
        self.from_currency_var.set(code)
        if not self.to_currency_var.get() or self.to_currency_var.get() == code:
            self.to_currency_var.set("MDL" if code != "MDL" else "EUR")
        self.notebook.select(0)
        self.amount_entry.focus_set()

    def _on_load_rates_clicked(self) -> None:
        if self.rates_service is None:
            return
        try:
            target_date = datetime.strptime(self.date_var.get().strip(), "%d.%m.%Y").date()
        except ValueError:
            self.notify("Invalid date format. Please use DD.MM.YYYY.", "error")
            return
        self.rates_caption_var.set("Loading official exchange rates...")

        def worker():
            try:
                res = self.rates_service.get_rates(target_date)
                self._queue.put(lambda: self._on_rates_tab_loaded(res))
            except Exception as exc:  # shown as a banner, never a pop-up
                msg = str(exc)
                self._queue.put(lambda: (self._fill_rates_table(),
                                         self.notify(f"Rates not loaded: {msg}", "error")))

        threading.Thread(target=worker, daemon=True).start()

    def _on_rates_tab_loaded(self, rates_result: RatesResult) -> None:
        self._on_rates_loaded(rates_result)
        if rates_result.notice:
            self.notify(rates_result.notice, "warn")
        else:
            self.notify(f"Loaded {len(rates_result.rates.currencies)} rates: "
                        f"{rates_result.provenance_label}.")

    def _on_enter_pressed(self, _event: Any = None) -> str:
        if "disabled" not in self.convert_button.state():
            self._on_convert_clicked()
        return "break"

    def _clear_form_result(self) -> None:
        self.hide_banner()
        self.validation_error_var.set("")
        self._clear_results()

    def _copy_result(self) -> None:
        text = "\n".join(v for v in (self.result_main_var.get(), self.result_reverse_var.get(),
                                     self.result_provenance_var.get()) if v)
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify("Result copied to the clipboard.")

    def _shift_date(self, days: int) -> None:
        try:
            current = datetime.strptime(self.date_var.get().strip(), "%d.%m.%Y").date()
        except ValueError:
            current = date.today()
        self.date_var.set((current + timedelta(days=days)).strftime("%d.%m.%Y"))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.convert_button.configure(text="Converting..." if busy else "Convert")
        self._update_convert_button_state()

    # --- Behaviour (unchanged logic) -----------------------------------------

    def _on_field_changed(self) -> None:
        self._update_convert_button_state()
        self._update_currency_names()

    def _update_convert_button_state(self) -> None:
        amount_text = self.amount_var.get().strip()
        from_code = self.from_currency_var.get().strip()
        to_code = self.to_currency_var.get().strip()

        is_complete = bool(amount_text and from_code and to_code) and not self._busy
        if is_complete:
            self.convert_button.state(["!disabled"])
        else:
            self.convert_button.state(["disabled"])

    def _swap_currencies(self) -> None:
        c_from = self.from_currency_var.get()
        c_to = self.to_currency_var.get()
        self.from_currency_var.set(c_to)
        self.to_currency_var.set(c_from)

    def _set_today_date(self) -> None:
        self.date_var.set(date.today().strftime("%d.%m.%Y"))

    def _clear_results(self) -> None:
        self.result_main_var.set("")
        self.result_reverse_var.set("")
        self.result_provenance_var.set("")
        self.result_notice_var.set("")

    def _load_initial_rates(self) -> None:
        """Fetch today's rates in the background on startup to populate currencies."""
        target_date = date.today()

        def worker():
            if self.rates_service is None:
                return
            try:
                res = self.rates_service.get_rates(target_date)
                self._queue.put(lambda: self._on_rates_loaded(res))
            except Exception as exc:
                # No network on startup: fill the currency lists from the saved rates
                # (FR-014/FR-017) and say so in the banner instead of failing silently.
                msg = str(exc)
                self._queue.put(lambda: self._on_initial_load_failed(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_initial_load_failed(self, message: str) -> None:
        cache = getattr(self.rates_service, "cache", None)
        rate_set = None
        if cache is not None:
            try:
                rate_set = cache.load()
            except Exception:
                rate_set = None
        if rate_set is None:
            self.notify(f"BNM is unavailable ({message}). Rates will be loaded on Convert.",
                        "warn", action=self._load_initial_rates, action_text="Retry")
            return
        self._on_rates_loaded(RatesResult(rates=rate_set, date=rate_set.date, source="cache",
                                          is_cached=True, notice="Using offline saved rates."))
        self.notify(f"BNM is unavailable: currency lists are filled from saved rates of "
                    f"{rate_set.date:%d.%m.%Y}.", "warn", action=self._load_initial_rates,
                    action_text="Retry")

    def _on_rates_loaded(self, rates_result: RatesResult) -> None:
        self.current_rates_result = rates_result
        self._update_currencies_from_rates(rates_result.rates)
        # Sensible default pair on first load: EUR -> MDL.
        if not self.from_currency_var.get() and not self.to_currency_var.get():
            currencies = rates_result.rates.currencies
            if "EUR" in currencies and "MDL" in currencies:
                self.from_currency_var.set("EUR")
                self.to_currency_var.set("MDL")
        self._update_header_stats()
        self._update_currency_names()
        self._fill_rates_table()

    def _update_currencies_from_rates(self, rate_set: RateSet) -> None:
        ordered = order_currencies(list(rate_set.currencies.keys()))
        self.set_currency_choices(ordered)

    def _on_convert_clicked(self) -> None:
        self.validation_error_var.set("")
        self.status_message_var.set("")
        self.hide_cache_offer()

        raw_amount = self.amount_var.get()
        try:
            parsed_amount = parse_amount(raw_amount)
        except ValidationError as err:
            self.validation_error_var.set(str(err))
            self._clear_results()
            return

        date_str = self.date_var.get().strip()
        try:
            target_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            self.validation_error_var.set("Invalid date format. Please use DD.MM.YYYY.")
            self._clear_results()
            return

        from_code = self.from_currency_var.get().strip()
        to_code = self.to_currency_var.get().strip()

        if not from_code or not to_code:
            self.validation_error_var.set("Please select both source and target currencies.")
            self._clear_results()
            return

        # If rates_service is available, perform rate lookup in background
        if self.rates_service is not None:
            self._perform_conversion_flow(parsed_amount, from_code, to_code, target_date)
        elif self.current_rates_result is not None:
            # Immediate conversion with existing rates
            try:
                conv = convert(parsed_amount, from_code, to_code, self.current_rates_result.rates)
                self._display_conversion(conv, self.current_rates_result)
            except Exception as exc:
                self.validation_error_var.set(str(exc))
                self._clear_results()

    def _perform_conversion_flow(
        self,
        amount: Decimal,
        from_code: str,
        to_code: str,
        target_date: date,
    ) -> None:
        self.status_message_var.set("Fetching official exchange rates...")
        self._set_busy(True)

        def worker():
            try:
                rates_result = self.rates_service.get_rates(target_date)
                conv = convert(amount, from_code, to_code, rates_result.rates)
                self._queue.put(lambda: self._on_conversion_success(conv, rates_result))
            except (NoRatesFoundError, InvalidDataError) as exc:
                err_msg = str(exc)
                self._queue.put(lambda: self._on_conversion_error(err_msg))
            except SourceUnavailableError as exc:
                err_msg = str(exc)
                self._queue.put(
                    lambda: self._handle_source_unavailable(err_msg, amount, from_code, to_code)
                )
            except Exception as exc:
                err_msg = str(exc)
                self._queue.put(lambda: self._on_conversion_error(f"Error: {err_msg}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_conversion_success(self, conv: Conversion, rates_result: RatesResult) -> None:
        self._set_busy(False)
        self.status_message_var.set("")
        self.validation_error_var.set("")
        self.current_rates_result = rates_result
        self._update_currencies_from_rates(rates_result.rates)
        self._update_header_stats()
        self._update_currency_names()
        self._fill_rates_table()
        self._display_conversion(conv, rates_result)

    def _display_conversion(self, conv: Conversion, rates_result: RatesResult) -> None:
        self.result_route_badge.configure(text=f"{conv.from_code} → {conv.to_code}")
        self.result_reverse_var.set(
            f"1 {conv.to_code} = {conv.reverse_rate_formatted} {conv.from_code}"
        )
        self.result_provenance_var.set(rates_result.provenance_label)
        if rates_result.notice:
            self.result_notice_var.set(rates_result.notice)
        else:
            self.result_notice_var.set("")
        self.result_main_var.set(
            f"{conv.amount} {conv.from_code} = {conv.result_formatted} {conv.to_code}"
        )
        self._record_history(conv)

    def _on_conversion_error(self, message: str) -> None:
        self._set_busy(False)
        self.status_message_var.set("")
        self.validation_error_var.set(message)
        self._clear_results()

    def _handle_source_unavailable(
        self,
        err_msg: str,
        amount: Decimal,
        from_code: str,
        to_code: str,
    ) -> None:
        self._set_busy(False)
        self.status_message_var.set("")
        self._clear_results()

        # Check if cache is available
        cached_rate_set = None
        if self.rates_service is not None and getattr(self.rates_service, "cache", None) is not None:
            try:
                cached_rate_set = self.rates_service.cache.load()
            except Exception:
                cached_rate_set = None

        if cached_rate_set is not None:
            self._cached_rate_set_to_offer = cached_rate_set
            self._pending_conversion_args = (amount, from_code, to_code)
            cached_date_str = cached_rate_set.date.strftime("%d.%m.%Y")
            offer_text = (
                f"BNM rate source is unavailable ({err_msg}).\n"
                f"Saved rates from {cached_date_str} are available. Use saved rates?"
            )
            self.validation_error_var.set(f"Connection error: {err_msg}")
            self.show_cache_offer(offer_text, self._on_accept_cache)
        else:
            self.validation_error_var.set(
                f"Cannot reach BNM exchange rate service ({err_msg}). No cached rates available."
            )

    def _on_accept_cache(self) -> None:
        if self._cached_rate_set_to_offer is None or not hasattr(self, "_pending_conversion_args"):
            self.hide_cache_offer()
            return

        rate_set = self._cached_rate_set_to_offer
        amount, from_code, to_code = self._pending_conversion_args
        self.hide_cache_offer()

        cached_result = RatesResult(
            rates=rate_set,
            date=rate_set.date,
            source="cache",
            is_cached=True,
            notice="Using offline saved rates.",
        )
        try:
            conv = convert(amount, from_code, to_code, rate_set)
            self._display_conversion(conv, cached_result)
            self.validation_error_var.set("")
            self.current_rates_result = cached_result
            self._update_header_stats()
            self._fill_rates_table()
        except Exception as exc:
            self.validation_error_var.set(f"Conversion with cached rates failed: {exc}")

    def _on_decline_cache(self) -> None:
        self.hide_cache_offer()
        self._cached_rate_set_to_offer = None
        self.validation_error_var.set("Rates unavailable: online connection failed and cached rates were declined.")

    def set_currency_choices(self, currencies: list[str]) -> None:
        """Update available currencies in selectors, preserving popular ordering."""
        ordered = order_currencies(currencies)
        self.available_currencies = ordered
        self.from_combo["values"] = self.available_currencies
        self.to_combo["values"] = self.available_currencies

    def show_cache_offer(self, message: str, on_accept: Callable[[], None]) -> None:
        self.cache_prompt_label.configure(text=message)
        self.hide_banner()
        self.cache_prompt_frame.pack(fill=tk.X, after=self.header)

    def hide_cache_offer(self) -> None:
        self.cache_prompt_frame.pack_forget()

    # --- History tab ---------------------------------------------------------

    def _record_history(self, conv: Conversion) -> None:
        try:
            self.history.add(conv)
        except OSError as exc:  # disk problem: the conversion itself is still shown
            self.notify(f"History not saved: {exc}", "warn")
        self._fill_history_table()

    def _fill_history_table(self) -> None:
        tree = self.history_tree
        tree.delete(*tree.get_children())
        entries = self.history.search(self.history_search_var.get())
        for i, entry in enumerate(entries):
            tags = []
            if i % 2:
                tags.append("alt")
            if entry.source == "cache":
                tags.append("cache")
            tree.insert("", tk.END, iid=str(entry.id), tags=tuple(tags), values=(
                entry.time, entry.text, entry.rate_date, entry.source))
        total = len(self.history)
        self.history_count_badge.configure(text=str(len(entries)))
        self.notebook.tab(self.history_tab, text=f"History ({total})" if total else "History")
        if total == 0:
            self.history_caption_var.set("No conversions yet. Each conversion is saved here.")
        elif len(entries) != total:
            self.history_caption_var.set(f"Found {len(entries)} of {total}.")
        else:
            self.history_caption_var.set(f"{total} saved, newest first.")
        self._update_history_buttons()

    def _selected_history_ids(self) -> list[int]:
        return [int(iid) for iid in self.history_tree.selection()]

    def _update_history_buttons(self) -> None:
        selected = self._selected_history_ids()
        self.history_repeat_button.state(["!disabled"] if len(selected) == 1 else ["disabled"])
        self.history_delete_button.state(["!disabled"] if selected else ["disabled"])
        has_rows = len(self.history) > 0
        for button in (self.history_clear_button, self.history_export_button):
            button.state(["!disabled"] if has_rows else ["disabled"])

    def repeat_selected(self) -> None:
        """Fill the form from the selected row and convert again at today's rate."""
        selected = self._selected_history_ids()
        if len(selected) != 1:
            return
        entry = self.history.get(selected[0])
        if entry is None:
            return
        self.amount_var.set(entry.amount)
        self.from_currency_var.set(entry.from_code)
        self.to_currency_var.set(entry.to_code)
        self.date_var.set(entry.rate_date)
        self.notebook.select(0)
        self._on_convert_clicked()

    def delete_selected(self) -> None:
        selected = self._selected_history_ids()
        if not selected:
            return
        removed = self.history.delete(selected)
        self._fill_history_table()
        self.notify(f"Deleted {removed} {'row' if removed == 1 else 'rows'} from the history.")

    def ask_clear_history(self) -> None:
        """Confirmation in the banner, not in a pop-up."""
        total = len(self.history)
        if not total:
            return
        self.notify(f"Delete all {total} conversions from the history?", "warn",
                    action=self.clear_history, action_text="Clear")

    def clear_history(self) -> None:
        removed = self.history.clear()
        self._fill_history_table()
        self.notify(f"History cleared ({removed} removed).")

    def _export_path(self, prefix: str) -> Path:
        return self.export_dir / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.csv"

    def _notify_exported(self, count: int, path: Path) -> None:
        action = None
        if hasattr(os, "startfile"):
            action = lambda: os.startfile(str(path.parent))  # Windows: opens the folder
        self.notify(f"Saved {count} rows: {path}", action=action, action_text="Open folder")

    def export_history_csv(self) -> None:
        """Exports what the table shows now (with the search filter)."""
        entries = self.history.search(self.history_search_var.get())
        if not entries:
            self.notify("Nothing to export: the history is empty.", "warn")
            return
        path = self._export_path("history")
        try:
            count = ConversionHistory.export_csv(entries, path)
        except OSError as exc:
            self.notify(f"CSV not saved: {exc}", "error")
            return
        self._notify_exported(count, path)

    def export_rates_csv(self) -> None:
        if self.current_rates_result is None:
            self.notify("Nothing to export: rates are not loaded yet.", "warn")
            return
        rate_set = self.current_rates_result.rates
        path = self._export_path(f"bnm_rates_{rate_set.date:%Y%m%d}")
        try:
            count = export_rates_csv(rate_set, path)
        except OSError as exc:
            self.notify(f"CSV not saved: {exc}", "error")
            return
        self._notify_exported(count, path)


def default_export_dir() -> Path:
    """CSV files go to Documents (or the home folder if there is none)."""
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()
