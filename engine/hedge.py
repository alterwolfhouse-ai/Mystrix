from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .indicators import rsi_wilder
from .divergence import bull_divergence, bear_divergence, valuewhen


@dataclass
class HedgeParams:
    # RSI / pivots (shared)
    rsi_length: int = 14
    rsi_overbought: int = 79
    rsi_oversold: int = 27
    lookbackLeft: int = 5
    lookbackRight: int = 5
    rangeUpper: int = 60
    rangeLower: int = 5

    # Risk / sizing (compounding)
    initial_capital: float = 10_000.0
    size_equity_pct: float = 0.50  # 50% equity per side
    fee_bps: float = 5.0

    # Advanced SL/TP
    init_stop_pct: float = 5.0
    trail_start_pct: float = 1.0
    trail_bump_pct: float = 2.0
    trail_step_pct: float = 5.0
    tp_half_pct: float = 7.0
    allow_stop_above_entry: bool = True
    # Experimental profit lock (disabled)
    lock_arm_pct: float = 0.0
    lock_profit_pct: float = 0.0
    cooldown_bars: int = 0


def _coerce(p: HedgeParams) -> HedgeParams:
    def _fi(x, d):
        try:
            return int(float(x))
        except Exception:
            return int(d)
    def _ff(x, d):
        try:
            return float(x)
        except Exception:
            return float(d)
    p.rsi_length = _fi(p.rsi_length, 14)
    p.rsi_overbought = _fi(p.rsi_overbought, 79)
    p.rsi_oversold = _fi(p.rsi_oversold, 27)
    p.lookbackLeft = _fi(p.lookbackLeft, 5)
    p.lookbackRight = _fi(p.lookbackRight, 5)
    p.rangeUpper = _fi(p.rangeUpper, 60)
    p.rangeLower = _fi(p.rangeLower, 5)
    p.initial_capital = _ff(p.initial_capital, 10_000.0)
    p.size_equity_pct = _ff(p.size_equity_pct, 0.50)
    p.fee_bps = _ff(p.fee_bps, 5.0)
    p.init_stop_pct = _ff(p.init_stop_pct, 5.0)
    p.trail_start_pct = _ff(p.trail_start_pct, 1.0)
    p.trail_bump_pct = _ff(p.trail_bump_pct, 2.0)
    p.trail_step_pct = _ff(p.trail_step_pct, 5.0)
    p.tp_half_pct = _ff(p.tp_half_pct, 7.0)
    p.allow_stop_above_entry = bool(p.allow_stop_above_entry)
    # experimental lock params disabled
    p.lock_arm_pct = 0.0
    p.lock_profit_pct = 0.0
    try:
        p.cooldown_bars = int(float(getattr(p, 'cooldown_bars', 0)))
    except Exception:
        p.cooldown_bars = 0
    return p


def _pct_ret_long(px: float, entry: float) -> float:
    return (px / entry - 1.0) * 100.0

def _pct_ret_short(px: float, entry: float) -> float:
    return (entry / px - 1.0) * 100.0


def backtest_hedged(symbol: str, df: pd.DataFrame, params: Dict) -> Tuple[Dict, List[dict], List[Tuple[pd.Timestamp, float]]]:
    p = _coerce(HedgeParams(**params))
    if df.empty:
        return ({
            "Total Return (%)": 0.0,
            "Num Trades": 0,
            "Ending Equity": p.initial_capital,
        }, [], [], [], [])

    fee_factor = p.fee_bps / 10_000.0
    equity = float(p.initial_capital)
    trades: List[dict] = []
    eq_series: List[Tuple[pd.Timestamp, float]] = []

    # Indicators
    rsi = rsi_wilder(df["close"], p.rsi_length).fillna(50)
    bull = bull_divergence(rsi, df["low"], p.lookbackLeft, p.lookbackRight, p.rangeLower, p.rangeUpper)
    bear = bear_divergence(rsi, df["high"], p.lookbackLeft, p.lookbackRight, p.rangeLower, p.rangeUpper)
    setup_bear = (rsi.shift(1) <= p.rsi_overbought) & (rsi > p.rsi_overbought)
    setup_bull = (rsi.shift(1) >= p.rsi_oversold) & (rsi < p.rsi_oversold)

    # LTF recently armed series
    idx = np.arange(len(df), dtype=float)
    lt_arm = (rsi < p.rsi_oversold)
    lt_last = np.where(lt_arm.values, idx, np.nan)
    lt_last = pd.Series(lt_last, index=df.index).ffill().values
    lt_bars = idx - np.where(np.isnan(lt_last), np.inf, lt_last)
    lt_recent = pd.Series(lt_bars <= float(max(1, p.lookbackLeft + p.lookbackRight)), index=df.index)

    st_arm = (rsi > p.rsi_overbought)
    st_last = np.where(st_arm.values, idx, np.nan)
    st_last = pd.Series(st_last, index=df.index).ffill().values
    st_bars = idx - np.where(np.isnan(st_last), np.inf, st_last)
    st_recent = pd.Series(st_bars <= float(max(1, p.lookbackLeft + p.lookbackRight)), index=df.index)

    # Position state (long & short independent)
    in_long = False; long_entry = np.nan; long_stop = np.nan; long_qty = 0.0; long_peak = 0.0; long_half_tp = False
    in_short = False; short_entry = np.nan; short_stop = np.nan; short_qty = 0.0; short_peak = 0.0; short_half_tp = False
    eqL = p.initial_capital * p.size_equity_pct
    eqS = p.initial_capital * p.size_equity_pct
    eq_series_long: List[Tuple[pd.Timestamp, float]] = []
    eq_series_short: List[Tuple[pd.Timestamp, float]] = []
    cdL = 0  # cooldown bars remaining for long re-entry
    cdS = 0  # cooldown bars remaining for short re-entry

    for i in range(len(df)):
        t = df.index[i]
        px = float(df["close"].iloc[i])
        # Cooldown ticks (decrement when flat on that side)
        if (not in_long) and cdL > 0:
            cdL -= 1
        if (not in_short) and cdS > 0:
            cdS -= 1

        # --- Long: manage
        if in_long:
            # update peak
            long_peak = max(long_peak, _pct_ret_long(px, long_entry))
            # experimental profit lock
            if (p.lock_arm_pct > 0) and (p.lock_profit_pct > 0) and (long_peak >= p.lock_arm_pct):
                lock_price = long_entry * (1 + p.lock_profit_pct/100.0)
                if lock_price > px:
                    lock_price = px
                long_stop = max(long_stop, lock_price)
            # partial TP (70%)
            if (not long_half_tp) and (long_peak >= p.tp_half_pct):
                exit_p = px
                part_qty = long_qty * 0.70
                pnl = (exit_p - long_entry) * part_qty
                fee = (exit_p * part_qty + long_entry * part_qty) * fee_factor
                pnl -= fee
                equity += pnl
                eq_series.append((t, equity))
                eqL += pnl
                eq_series_long.append((t, eqL))
                trades.append({"symbol":symbol, "t": t.isoformat(), "side":"long", "type":"exit_half_tp", "price": exit_p, "qty": part_qty, "pnl": pnl})
                long_qty -= part_qty
                long_half_tp = True
            # trailing disabled (only initial stop remains)
            # stop hit?
            if float(df["low"].iloc[i]) <= long_stop:
                lo_i = float(df["low"].iloc[i]); hi_i = float(df["high"].iloc[i])
                # Fill price must be within bar range for realism
                exit_p = min(max(long_stop, lo_i), hi_i)
                pnl = (exit_p - long_entry) * long_qty
                fee = (exit_p * long_qty + long_entry * long_qty) * fee_factor
                pnl -= fee
                equity += pnl
                eq_series.append((t, equity))
                eqL += pnl
                eq_series_long.append((t, eqL))
                trades.append({"symbol":symbol, "t": t.isoformat(), "side":"long", "type":"exit_sl", "price": exit_p, "qty": long_qty, "pnl": pnl})
                in_long=False
                cdL = int(p.cooldown_bars or 0)
        # --- Long: normal exit
        if in_long and bool(setup_bear.iloc[i]) and bool(bear.iloc[i]):
            exit_p = px
            pnl = (exit_p - long_entry) * long_qty
            fee = (exit_p * long_qty + long_entry * long_qty) * fee_factor
            pnl -= fee
            equity += pnl
            eq_series.append((t, equity))
            trades.append({"symbol":symbol, "t": t.isoformat(), "side":"long", "type":"exit_normal", "price": exit_p, "qty": long_qty, "pnl": pnl})
            in_long=False

        # --- Short: manage
        if in_short:
            short_peak = max(short_peak, _pct_ret_short(px, short_entry))
            if (p.lock_arm_pct > 0) and (p.lock_profit_pct > 0) and (short_peak >= p.lock_arm_pct):
                lock_price_s = short_entry * (1 - p.lock_profit_pct/100.0)
                short_stop = min(short_stop, lock_price_s)
            if (not short_half_tp) and (short_peak >= p.tp_half_pct):
                exit_p = px
                part_qty = short_qty * 0.70
                pnl = (short_entry - exit_p) * part_qty
                fee = (exit_p * part_qty + short_entry * part_qty) * fee_factor
                pnl -= fee
                equity += pnl
                eq_series.append((t, equity))
                eqS += pnl
                eq_series_short.append((t, eqS))
                trades.append({"symbol":symbol, "t": t.isoformat(), "side":"short", "type":"exit_half_tp", "price": exit_p, "qty": part_qty, "pnl": pnl})
                short_qty -= part_qty
                short_half_tp = True
            # trailing disabled (only initial stop remains)
            if float(df["high"].iloc[i]) >= short_stop:
                lo_i = float(df["low"].iloc[i]); hi_i = float(df["high"].iloc[i])
                # Fill price must be within bar range for realism
                exit_p = min(max(short_stop, lo_i), hi_i)
                pnl = (short_entry - exit_p) * short_qty
                fee = (exit_p * short_qty + short_entry * short_qty) * fee_factor
                pnl -= fee
                equity += pnl
                eq_series.append((t, equity))
                eqS += pnl
                eq_series_short.append((t, eqS))
                trades.append({"symbol":symbol, "t": t.isoformat(), "side":"short", "type":"exit_sl", "price": exit_p, "qty": short_qty, "pnl": pnl})
                in_short=False
                cdS = int(p.cooldown_bars or 0)
        if in_short and bool(setup_bull.iloc[i]) and bool(bull.iloc[i]):
            exit_p = px
            pnl = (short_entry - exit_p) * short_qty
            fee = (exit_p * short_qty + short_entry * short_qty) * fee_factor
            pnl -= fee
            equity += pnl
            eq_series.append((t, equity))
            trades.append({"symbol":symbol, "t": t.isoformat(), "side":"short", "type":"exit_normal", "price": exit_p, "qty": short_qty, "pnl": pnl})
            in_short=False

        # --- Entries (can be concurrent / hedged)
        if (not in_long) and (cdL <= 0) and bool(bull.iloc[i]) and bool(lt_recent.iloc[i]):
            long_entry = px
            long_qty = max(0.0, (equity * p.size_equity_pct) / max(1e-9, long_entry))
            fee = long_entry * long_qty * fee_factor
            equity -= fee
            long_stop = long_entry * (1 - p.init_stop_pct/100.0)
            long_peak = 0.0
            long_half_tp = False
            in_long = True
            trades.append({"symbol":symbol, "t": t.isoformat(), "side":"long", "type":"enter", "price": long_entry, "qty": long_qty, "stop": long_stop})

        if (not in_short) and (cdS <= 0) and bool(bear.iloc[i]) and bool(st_recent.iloc[i]):
            short_entry = px
            short_qty = max(0.0, (equity * p.size_equity_pct) / max(1e-9, short_entry))
            fee = short_entry * short_qty * fee_factor
            equity -= fee
            short_stop = short_entry * (1 + p.init_stop_pct/100.0)
            short_peak = 0.0
            short_half_tp = False
            in_short = True
            trades.append({"symbol":symbol, "t": t.isoformat(), "side":"short", "type":"enter", "price": short_entry, "qty": short_qty, "stop": short_stop})

    # Metrics
    exits = [t for t in trades if t.get("type","!").startswith("exit")]
    total_return = (equity / p.initial_capital - 1.0) * 100.0
    num_tr = sum(1 for t in trades if t.get("type")=='enter')
    win = sum(1 for t in exits if (t.get('pnl',0)>0))
    winrate = (win/len(exits)*100.0) if exits else 0.0
    metrics = {
        "Total Return (%)": round(total_return,2),
        "Num Trades": num_tr,
        "Win Rate (%)": round(winrate,2),
        "Ending Equity": round(equity,2)
    }
    # Add cumulative PnL
    cum = 0.0
    for t in trades:
        if t.get('pnl') is not None:
            cum += float(t.get('pnl',0))
        t['total_pnl'] = round(cum, 2)
    return metrics, trades, eq_series, eq_series_long, eq_series_short
