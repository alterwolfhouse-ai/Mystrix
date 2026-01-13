"""
Trade manager: sizing and simple risk constraints.

This module provides helpers for percent-of-equity sizing and simple
session risk rules. It is intentionally minimal and idempotent.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InstrumentInfo:
    tick_size: float = 0.01
    step_size: float = 0.001


def round_step(value: float, step: float) -> float:
    if step <= 0:
        return float(value)
    return float(int(value / step) * step)


def position_size(equity: float, entry: float, stop: float, risk_pct: float, step_size: float) -> float:
    risk_amt = max(0.0, equity) * max(0.0, risk_pct)
    per_unit = abs(entry - stop)
    if per_unit <= 0 or entry <= 0:
        return 0.0
    qty = risk_amt / per_unit
    return round_step(qty, step_size)

