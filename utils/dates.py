from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional


def _parse_date(s: str) -> date:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    raise ValueError("invalid date format (use DD-MM-YYYY or YYYY-MM-DD)")


def norm_date(s: str) -> str:
    """Normalize incoming date strings into YYYY-MM-DD when possible."""
    return _parse_date(s).strftime("%Y-%m-%d")


def validate_date_range(start: str, end: str, max_days: Optional[int] = None) -> None:
    s_date = _parse_date(start)
    e_date = _parse_date(end)
    if s_date > e_date:
        raise ValueError("start date must be on or before end date")
    if max_days is None:
        env = os.environ.get("MAX_BACKTEST_DAYS")
        if env:
            try:
                max_days = int(env)
            except Exception:
                max_days = None
    if max_days is not None and max_days > 0:
        span = (e_date - s_date).days
        if span > max_days:
            raise ValueError(f"date range too large (max {max_days} days)")
