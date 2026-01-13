from __future__ import annotations

from datetime import datetime


def norm_date(s: str) -> str:
    """Normalize incoming date strings into YYYY-MM-DD when possible."""
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return s
