from __future__ import annotations

"""
Short engine (Core 2) mirroring Pine Long structure but for bearish setups.

Defaults:
- rsi_len=15, ob=81, os=17, max_wait=15, pivots 5/5, percent_stop=0.015, cooldown 20 bars
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

from .indicators import rsi_wilder
from .divergence import bear_divergence, bull_divergence, valuewhen


@dataclass
class ShortParams:
    rsi_length: int = 15
    rsi_overbought: int = 81
    rsi_oversold: int = 17
    lookbackLeft: int = 5
    lookbackRight: int = 5
    rangeUpper: int = 60
    rangeLower: int = 5
    use_pct_stop: float = 0.015
    max_wait_bars: int = 15
    cooldownBars: int = 20
    fee_bps: float = 5.0
    initial_capital: float = 10_000.0
    percent_risk: float = 0.10


class PineShortEngine:
    def __init__(self, params: Optional[Dict] = None):
        p = ShortParams()
        # Ensure attribute exists early to avoid AttributeError in edge cases
        # Experimental lock profit disabled
        p.lock_arm_pct = 0.0
        p.lock_profit_pct = 0.0
        self.p = p
        if params:
            for k, v in params.items():
                if hasattr(p, k):
                    setattr(p, k, v)
        if p.rsi_overbought < p.rsi_oversold:
            p.rsi_overbought, p.rsi_oversold = p.rsi_oversold, p.rsi_overbought
        # Coerce param types\n        def _to_int(x, default=0):\n            try:\n                return int(float(x))\n            except Exception:\n                return int(default)\n        def _to_float(x, default=0.0):\n            try:\n                return float(x)\n            except Exception:\n                return float(default)\n        p.rsi_length = _to_int(p.rsi_length, 15)\n        p.rsi_overbought = _to_int(p.rsi_overbought, 81)\n        p.rsi_oversold = _to_int(p.rsi_oversold, 17)\n        p.lookbackLeft = _to_int(p.lookbackLeft, 5)\n        p.lookbackRight = _to_int(p.lookbackRight, 5)\n        p.rangeUpper = _to_int(p.rangeUpper, 60)\n        p.rangeLower = _to_int(p.rangeLower, 5)\n        p.max_wait_bars = _to_int(p.max_wait_bars, 15)\n        p.cooldownBars = _to_int(p.cooldownBars, 20)\n        p.use_pct_stop = _to_float(p.use_pct_stop, 0.015)\n        p.initial_capital = _to_float(p.initial_capital, 10000.0)\n        p.percent_risk = _to_float(p.percent_risk, 0.10)\n        self.p = p

    def _series(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        rsi = rsi_wilder(df["close"], self.p.rsi_length)
        return {"rsi": rsi}

    def _crossunder(self, s: pd.Series, level: float) -> pd.Series:
        prev = s.shift(1)
        return (prev >= level) & (s < level)

    def _crossover(self, s: pd.Series, level: float) -> pd.Series:
        prev = s.shift(1)
        return (prev <= level) & (s > level)

    def backtest(self, symbol: str, df: pd.DataFrame) -> Tuple[Dict, List[dict]]:
        if df.empty or len(df) < max(200, self.p.lookbackLeft + self.p.lookbackRight + 20):
            return ({
                "Total Return (%)": 0.0,
                "Num Trades": 0,
                "Win Rate (%)": 0.0,
                "Avg P&L": 0.0,
                "Sharpe": 0.0,
                "Ending Equity": self.p.initial_capital,
                "Max Drawdown (%)": 0.0,
            }, [])

        rsi = self._series(df)["rsi"].fillna(50)
        bearCond = bear_divergence(rsi, df["high"], self.p.lookbackLeft, self.p.lookbackRight, self.p.rangeLower, self.p.rangeUpper)
        bullCond = bull_divergence(rsi, df["low"], self.p.lookbackLeft, self.p.lookbackRight, self.p.rangeLower, self.p.rangeUpper)
        rsi_setup_short = self._crossunder(rsi, self.p.rsi_overbought)
        rsi_setup_bull = self._crossover(rsi, self.p.rsi_oversold)

        in_pos = False
        entry = np.nan
        stop = np.nan
        qty = 0.0
        fee_factor = self.p.fee_bps / 10_000.0
        equity = float(self.p.initial_capital)
        trades: List[dict] = []
        cooldown = 0
        runup_peak = 0.0

        highR = df["high"].shift(self.p.lookbackRight)

        # Precompute recently armed
        # Arm when RSI spends time in overbought or just crossed down from it
        cond = rsi >= self.p.rsi_overbought
        idx = np.arange(len(cond), dtype=float)
        last_true = np.where(cond.values, idx, np.nan)
        last_true = pd.Series(last_true, index=df.index).ffill().values
        bars_since = idx - np.where(np.isnan(last_true), np.inf, last_true)
        recently_armed = pd.Series(bars_since <= float(self.p.max_wait_bars), index=df.index)

        dd_peak = equity
        dd_min = equity

        for i in range(len(df)):
            price = float(df["close"].iloc[i])
            t = df.index[i]

            if cooldown > 0 and not in_pos:
                cooldown -= 1

            # entry
            if (not in_pos) and (recently_armed.iloc[i] or bool(rsi_setup_short.iloc[i])) and bool(bearCond.iloc[i]) and cooldown == 0:
                wave_high = float(valuewhen(bearCond, highR, 0).iloc[i]) if not np.isnan(valuewhen(bearCond, highR, 0).iloc[i]) else np.nan
                entry_p = price
                pct_stop = entry_p * (1 + self.p.use_pct_stop)
                stop_p = pct_stop
                if not np.isnan(wave_high):
                    stop_p = max(wave_high, pct_stop)
                risk_val = equity * self.p.percent_risk
                qty = max(0.0, risk_val / max(1e-9, entry_p))
                equity -= entry_p * qty * fee_factor
                in_pos = True
                entry = entry_p
                stop = stop_p
                runup_peak = 0.0
                trades.append({"symbol":symbol, "t": t.isoformat(), "type":"enter", "price": entry, "qty": qty})

            # exit via bull divergence after OS setup
            if in_pos and bool(rsi_setup_bull.iloc[i]) and bool(bullCond.iloc[i]):
                exit_p = price
                pnl = (entry - exit_p) * qty
                pnl -= exit_p * qty * fee_factor
                equity += pnl
                in_pos = False
                cooldown = self.p.cooldownBars
                trades.append({"symbol":symbol, "t": t.isoformat(), "type":"exit_normal", "price": exit_p, "qty": qty, "pnl": pnl})

            # stop
            if in_pos and float(df["high"].iloc[i]) >= stop:
                exit_p = stop
                pnl = (entry - exit_p) * qty
                pnl -= exit_p * qty * fee_factor
                equity += pnl
                in_pos = False
                cooldown = self.p.cooldownBars
                trades.append({"symbol":symbol, "t": t.isoformat(), "type":"exit_sl", "price": exit_p, "qty": qty, "pnl": pnl})

            # Experimental: lock profit stop after runup >= arm
            if in_pos:
                try:
                    ru = (entry / price - 1.0) * 100.0
                except Exception:
                    ru = 0.0
                runup_peak = max(runup_peak, ru)
                if (self.p.lock_arm_pct > 0) and (self.p.lock_profit_pct > 0) and (runup_peak >= self.p.lock_arm_pct):
                    lock_st = entry * (1 - self.p.lock_profit_pct/100.0)
                    stop = min(stop, lock_st)

            dd_peak = max(dd_peak, equity)
            dd_min = min(dd_min, equity)

        max_dd_pct = 0.0 if dd_peak <= 0 else (1.0 - (dd_min/dd_peak)) * 100.0
        metrics = {
            "Total Return (%)": round((equity/self.p.initial_capital - 1.0)*100, 2),
            "Num Trades": int(sum(1 for t in trades if t.get("type") == "enter")),
            "Win Rate (%)": round(100.0 * (np.mean([t.get("pnl", 0) > 0 for t in trades if t["type"].startswith("exit")]) if any(t["type"].startswith("exit") for t in trades) else 0.0), 2),
            "Avg P&L": round(np.mean([t.get("pnl", 0) for t in trades if t["type"].startswith("exit")]) if any(t["type"].startswith("exit") for t in trades) else 0.0, 2),
            "Sharpe": 0.0,
            "Ending Equity": round(equity,2),
            "Max Drawdown (%)": round(max_dd_pct,2),
        }
        return metrics, trades
