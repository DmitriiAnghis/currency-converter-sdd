"""Pytest shared configuration and fixtures."""

import os
import sys
import pytest

_tcl_dir = os.path.join(sys.prefix, "tcl", "tcl8.6")
_tk_dir = os.path.join(sys.prefix, "tcl", "tk8.6")
if "TCL_LIBRARY" not in os.environ and os.path.exists(_tcl_dir):
    os.environ["TCL_LIBRARY"] = _tcl_dir
if "TK_LIBRARY" not in os.environ and os.path.exists(_tk_dir):
    os.environ["TK_LIBRARY"] = _tk_dir


@pytest.fixture(scope="session")
def tk_session_root():
    """Create a persistent Tk root for the test session to avoid repeated Tcl re-init."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def disallow_network_access(monkeypatch):
    """Enforce that no test uses live network connections."""
    import socket

    def guarded_connect(*args, **kwargs):
        raise RuntimeError("Tests must not access the live network!")

    monkeypatch.setattr(socket, "create_connection", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
