"""
HTF latch for reactivation logic.

Runs the long engine on 30m to determine whether a new long cycle has started
after a prior close. This is a minimal latch; production logic may track state per symbol.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from .pine_long import PineLongEngine


class HTFLatch:
    def __init__(self):
        self.state: Dict[str, str] = {}  # symbol -> 'open'|'closed'

    def allows_long(self, symbol: str, df30m: pd.DataFrame) -> bool:
        if df30m is None or df30m.empty:
            return True
        eng = PineLongEngine()
        metrics, trades = eng.backtest(symbol, df30m)
        if not trades:
            return True
        last = trades[-1]
        # allow if last trade type is 'enter' (started new cycle)
        return str(last.get("type")) == "enter"

