"""Graphical user interface for BNM Currency Converter using Tkinter."""

from datetime import date
from decimal import Decimal
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from converter.validation import ValidationError, parse_amount


POPULAR_CURRENCIES = ["EUR", "USD", "RON", "UAH", "RUB", "GBP"]


class ConverterApp:
    """Desktop GUI application for currency conversion."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        rates_service: Optional[Any] = None,
        converter: Optional[Any] = None,
    ) -> None:
        self.root = root if root is not None else tk.Tk()
        self.root.title("BNM Currency Converter")
        self.root.geometry("520x640")
        self.root.minsize(460, 580)

        self.rates_service = rates_service
        self.converter = converter

        # State variables
        self.amount_var = tk.StringVar()
        self.from_currency_var = tk.StringVar()
        self.to_currency_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().strftime("%d.%m.%Y"))

        self.status_message_var = tk.StringVar()
        self.validation_error_var = tk.StringVar()
        self.result_main_var = tk.StringVar()
        self.result_reverse_var = tk.StringVar()
        self.result_provenance_var = tk.StringVar()
        self.result_notice_var = tk.StringVar()

        self.available_currencies: list[str] = ["MDL", "EUR", "USD", "RON", "UAH", "RUB", "GBP"]
        self.current_rates_result = None

        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._update_convert_button_state()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Configure color palette
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
        header_frame.pack(fill=tk.X, pady=(0, 16))

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
        date_frame.pack(fill=tk.X, pady=(0, 14))

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

        # Validation message label
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

    def _on_convert_clicked(self) -> None:
        # Clear previous errors and results
        self.validation_error_var.set("")
        raw_amount = self.amount_var.get()

        try:
            parsed_amount = parse_amount(raw_amount)
        except ValidationError as err:
            self.validation_error_var.set(str(err))
            self._clear_results()
            return

        # If rates_service is provided, trigger conversion workflow (implemented in Phase 4)
        if self.rates_service is not None and self.converter is not None:
            self._execute_conversion(parsed_amount)

    def _execute_conversion(self, amount: Decimal) -> None:
        # Placeholder for Phase 4 integration
        pass

    def _on_accept_cache(self) -> None:
        # Placeholder for Phase 6 offline flow
        pass

    def _on_decline_cache(self) -> None:
        self.cache_prompt_frame.pack_forget()

    def set_currency_choices(self, currencies: list[str]) -> None:
        """Update available currencies in selectors, preserving popular ordering."""
        self.available_currencies = list(currencies)
        self.from_combo["values"] = self.available_currencies
        self.to_combo["values"] = self.available_currencies

    def show_cache_offer(self, message: str, on_accept: Callable[[], None]) -> None:
        self.cache_prompt_label.configure(text=message)
        self._cache_accept_callback = on_accept
        self.cache_prompt_frame.pack(fill=tk.X, pady=(0, 10), before=self.result_card)

    def hide_cache_offer(self) -> None:
        self.cache_prompt_frame.pack_forget()
