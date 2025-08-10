"""
Utilities for consistent UTF-8 console behavior on Windows and safe console text.
"""

from __future__ import annotations
import sys
import os


def force_utf8_stdio() -> None:
    """Force UTF-8 mode for stdio where possible; safe on Windows PowerShell 7.

    - Enables PEP 540 UTF-8 mode via PYTHONUTF8 unless already set.
    - Reconfigures stdout/stderr to utf-8 with errors="replace" when supported.
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Ignore if streams do not support reconfigure (older embedders)
        pass


def safe_console_text(message: str) -> str:
    """Return message if console is UTF-8; else ASCII-sanitize known symbols.

    We only sanitize for console printing; file logs should remain full Unicode.
    """
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf-8" in enc or "utf8" in enc:
        return message
    # Basic fallback replacement for Greek letters commonly used in stats
    return (
        message
        .replace("μ", "mu")
        .replace("σ", "sigma")
    )


