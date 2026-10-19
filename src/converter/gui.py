"""Graphical user interface for BNM Currency Converter using Tkinter."""

from datetime import date, datetime
from decimal import Decimal
import os
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


class ConverterApp:
    """Desktop GUI application for currency conversion."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        rates_service: Optional[RatesService] = None,
    ) -> None:
        self.root = root if root is not None else tk.Tk()
        self.root.title("BNM Currency Converter")
        self.root.geometry("520x680")
        self.root.minsize(460, 600)

        self.rates_service = rates_service

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

        initial_defaults = ["EUR", "USD", "RON", "UAH", "RUB", "GBP", "MDL"]
        self.available_currencies: list[str] = order_currencies(initial_defaults)
        self.current_rates_result: Optional[RatesResult] = None
        self._cached_rate_set_to_offer: Optional[RateSet] = None

        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._update_convert_button_state()
        self._schedule_queue_processing()

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

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg="#f1f5f9")  # Slate-100

        style.configure(".", font=("Segoe UI", 10), background="#f1f5f9", foreground="#0f172a")

        # Header styles
        style.configure(
            "Header.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground="#1e293b",
            background="#f1f5f9",
        )
        style.configure(
            "Subheader.TLabel",
            font=("Segoe UI", 9),
            foreground="#64748b",
            background="#f1f5f9",
        )

        # Card frames
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("InnerCard.TFrame", background="#ffffff")

        # Labels
        style.configure(
            "FieldLabel.TLabel",
            font=("Segoe UI", 9, "bold"),
            foreground="#334155",
            background="#ffffff",
        )
        style.configure(
            "Status.TLabel",
            font=("Segoe UI", 9, "italic"),
            foreground="#2563eb",
            background="#ffffff",
        )
        style.configure(
            "Error.TLabel",
            font=("Segoe UI", 9, "bold"),
            foreground="#dc2626",
            background="#ffffff",
        )
        style.configure(
            "Notice.TLabel",
            font=("Segoe UI", 9, "italic"),
            foreground="#d97706",
            background="#ffffff",
        )

        # Buttons
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 11, "bold"),
            background="#2563eb",
            foreground="#ffffff",
            padding=(12, 8),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("disabled", "#94a3b8")],
            foreground=[("disabled", "#ffffff")],
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9),
            background="#e2e8f0",
            foreground="#1e293b",
            padding=(6, 4),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#cbd5e1")],
        )

        # Result display styles
        style.configure(
            "ResultMain.TLabel",
            font=("Segoe UI", 18, "bold"),
            foreground="#0f172a",
            background="#ffffff",
        )
        style.configure(
            "ResultSub.TLabel",
            font=("Segoe UI", 10),
            foreground="#475569",
            background="#ffffff",
        )
        style.configure(
            "Provenance.TLabel",
            font=("Segoe UI", 9, "bold"),
            foreground="#059669",
            background="#ffffff",
        )

    def _build_ui(self) -> None:
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Title & Subtitle
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_label = ttk.Label(header_frame, text="BNM Currency Converter", style="Header.TLabel")
        title_label.pack(anchor=tk.W)
        subtitle_label = ttk.Label(
            header_frame,
            text="Official exchange rates from the National Bank of Moldova",
            style="Subheader.TLabel",
        )
        subtitle_label.pack(anchor=tk.W)

        # Form Card
        form_card = ttk.Frame(main_container, style="Card.TFrame", padding=16)
        form_card.pack(fill=tk.X, pady=(0, 14))

        # Amount Entry
        amount_lbl = ttk.Label(form_card, text="AMOUNT", style="FieldLabel.TLabel")
        amount_lbl.pack(anchor=tk.W, pady=(0, 4))

        self.amount_entry = ttk.Entry(
            form_card,
            textvariable=self.amount_var,
            font=("Segoe UI", 12),
        )
        self.amount_entry.pack(fill=tk.X, pady=(0, 10))

        # Currency Selectors
        currencies_frame = ttk.Frame(form_card, style="InnerCard.TFrame")
        currencies_frame.pack(fill=tk.X, pady=(0, 10))

        from_col = ttk.Frame(currencies_frame, style="InnerCard.TFrame")
        from_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(from_col, text="FROM", style="FieldLabel.TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.from_combo = ttk.Combobox(
            from_col,
            textvariable=self.from_currency_var,
            values=self.available_currencies,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self.from_combo.pack(fill=tk.X)

        # Swap button
        swap_btn = ttk.Button(
            currencies_frame,
            text="⇄",
            width=3,
            style="Secondary.TButton",
            command=self._swap_currencies,
        )
        swap_btn.pack(side=tk.LEFT, padx=8, pady=(18, 0))

        to_col = ttk.Frame(currencies_frame, style="InnerCard.TFrame")
        to_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(to_col, text="TO", style="FieldLabel.TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.to_combo = ttk.Combobox(
            to_col,
            textvariable=self.to_currency_var,
            values=self.available_currencies,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self.to_combo.pack(fill=tk.X)

        # Date Selector
        date_frame = ttk.Frame(form_card, style="InnerCard.TFrame")
        date_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(date_frame, text="RATE DATE (DD.MM.YYYY)", style="FieldLabel.TLabel").pack(
            anchor=tk.W, pady=(0, 4)
        )
        date_row = ttk.Frame(date_frame, style="InnerCard.TFrame")
        date_row.pack(fill=tk.X)

        self.date_entry = ttk.Entry(
            date_row,
            textvariable=self.date_var,
            font=("Segoe UI", 10),
        )
        self.date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        today_btn = ttk.Button(
            date_row,
            text="Today",
            style="Secondary.TButton",
            command=self._set_today_date,
        )
        today_btn.pack(side=tk.LEFT, padx=(6, 0))

        # Status / Loading message
        self.status_label = ttk.Label(
            form_card,
            textvariable=self.status_message_var,
            style="Status.TLabel",
            wraplength=440,
        )
        self.status_label.pack(anchor=tk.W, pady=(0, 4))

        # Validation / Error message
        self.validation_label = ttk.Label(
            form_card,
            textvariable=self.validation_error_var,
            style="Error.TLabel",
            wraplength=440,
        )
        self.validation_label.pack(anchor=tk.W, pady=(0, 8))

        # Convert Button
        self.convert_button = ttk.Button(
            form_card,
            text="Convert",
            style="Primary.TButton",
            command=self._on_convert_clicked,
        )
        self.convert_button.pack(fill=tk.X)

        # Offline / Cache offer prompt frame (hidden by default)
        self.cache_prompt_frame = ttk.Frame(main_container, style="Card.TFrame", padding=12)
        self.cache_prompt_label = ttk.Label(
            self.cache_prompt_frame,
            text="",
            style="FieldLabel.TLabel",
            wraplength=440,
        )
        self.cache_prompt_label.pack(anchor=tk.W, pady=(0, 8))
        cache_buttons_row = ttk.Frame(self.cache_prompt_frame, style="InnerCard.TFrame")
        cache_buttons_row.pack(fill=tk.X)
        self.cache_accept_btn = ttk.Button(
            cache_buttons_row,
            text="Use Saved Rates",
            style="Primary.TButton",
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

        # Results Card
        self.result_card = ttk.Frame(main_container, style="Card.TFrame", padding=16)
        self.result_card.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.result_main_lbl = ttk.Label(
            self.result_card,
            textvariable=self.result_main_var,
            style="ResultMain.TLabel",
            wraplength=440,
        )
        self.result_main_lbl.pack(anchor=tk.W, pady=(0, 4))

        self.result_reverse_lbl = ttk.Label(
            self.result_card,
            textvariable=self.result_reverse_var,
            style="ResultSub.TLabel",
            wraplength=440,
        )
        self.result_reverse_lbl.pack(anchor=tk.W, pady=(0, 4))

        self.result_notice_lbl = ttk.Label(
            self.result_card,
            textvariable=self.result_notice_var,
            style="Notice.TLabel",
            wraplength=440,
        )
        self.result_notice_lbl.pack(anchor=tk.W, pady=(0, 4))

        self.result_provenance_lbl = ttk.Label(
            self.result_card,
            textvariable=self.result_provenance_var,
            style="Provenance.TLabel",
            wraplength=440,
        )
        self.result_provenance_lbl.pack(anchor=tk.W, pady=(0, 4))

    def _bind_events(self) -> None:
        self.amount_var.trace_add("write", lambda *_: self._on_field_changed())
        self.from_currency_var.trace_add("write", lambda *_: self._on_field_changed())
        self.to_currency_var.trace_add("write", lambda *_: self._on_field_changed())

    def _on_field_changed(self) -> None:
        self._update_convert_button_state()

    def _update_convert_button_state(self) -> None:
        amount_text = self.amount_var.get().strip()
        from_code = self.from_currency_var.get().strip()
        to_code = self.to_currency_var.get().strip()

        is_complete = bool(amount_text and from_code and to_code)
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
            except Exception:
                # Silent failure on startup; user will see errors if they click Convert
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_rates_loaded(self, rates_result: RatesResult) -> None:
        self.current_rates_result = rates_result
        self._update_currencies_from_rates(rates_result.rates)

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
        self.status_message_var.set("")
        self.validation_error_var.set("")
        self.current_rates_result = rates_result
        self._update_currencies_from_rates(rates_result.rates)
        self._display_conversion(conv, rates_result)

    def _display_conversion(self, conv: Conversion, rates_result: RatesResult) -> None:
        self.result_main_var.set(
            f"{conv.amount} {conv.from_code} = {conv.result_formatted} {conv.to_code}"
        )
        self.result_reverse_var.set(
            f"1 {conv.to_code} = {conv.reverse_rate_formatted} {conv.from_code}"
        )
        self.result_provenance_var.set(rates_result.provenance_label)
        if rates_result.notice:
            self.result_notice_var.set(rates_result.notice)
        else:
            self.result_notice_var.set("")

    def _on_conversion_error(self, message: str) -> None:
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
        self.cache_prompt_frame.pack(fill=tk.X, pady=(0, 10), before=self.result_card)

    def hide_cache_offer(self) -> None:
        self.cache_prompt_frame.pack_forget()
