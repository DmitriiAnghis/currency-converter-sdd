"""Desktop entry point for BNM Currency Converter."""

import tkinter as tk

from converter.bnm_client import BnmClient
from converter.cache import RateCache
from converter.gui import ConverterApp
from converter.rates_service import RatesService


def main() -> None:
    """Launch the BNM Currency Converter desktop application."""
    root = tk.Tk()
    cache = RateCache()
    service = RatesService(client=BnmClient(), cache=cache)
    app = ConverterApp(root=root, rates_service=service)
    root.mainloop()


if __name__ == "__main__":
    main()
