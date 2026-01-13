from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .indicators import rsi_wilder
from .divergence import bull_divergence, bear_divergence, valuewhen
from .data import mintick, resample_ohlcv


@dataclass
class PineParams:
    rsi_length: int = 14
    rsi_overbought: int = 79
    rsi_oversold: int = 27
    lookbackLeft: int = 5
    lookbackRight: int = 5
    rangeUpper: int = 60
    rangeLower: int = 5
    calculateDivergence: bool = True
    use_pct_stop: float = 0.018  # 1.8%
    max_wait_bars: int = 25
    cooldownBars: int = 15
    fee_bps: float = 5.0
    initial_capital: float = 10_000.0
    percent_risk: float = 0.10  # percent equity sized (TradingView default_qty_value)
    # HTF gate
    enableHTFGate: bool = False
    htfTF: str = "30m"
    htf_pct_stop: float = 0.20  # 20% HTF stop closes gate
    # HTF-specific parameters (default to LTF-like values)
    htf_rsi_length: int = 14
    htf_rsi_overbought: int = 79
    htf_rsi_oversold: int = 27
    htf_lookbackLeft: int = 5
    htf_lookbackRight: int = 5
    htf_rangeUpper: int = 60
    htf_rangeLower: int = 5
    htf_max_wait_bars: int = 25
    # Experimental: lock profit (disabled)
    lock_arm_pct: float = 0.0
    lock_profit_pct: float = 0.0


class PineLongEngine:
    def __init__(self, params: Optional[Dict] = None):
        p = PineParams()
        if params:
            for k, v in params.items():
                if hasattr(p, k):
                    setattr(p, k, v)
        if p.rsi_overbought < p.rsi_oversold:
            p.rsi_overbought, p.rsi_oversold = p.rsi_oversold, p.rsi_overbought
        def _to_int(x, default=0):
            try:
                return int(float(x))
            except Exception:
                return int(default)
        def _to_float(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return float(default)
        p.rsi_length = _to_int(p.rsi_length, 14)
        p.rsi_overbought = _to_int(p.rsi_overbought, 79)
        p.rsi_oversold = _to_int(p.rsi_oversold, 27)
        p.lookbackLeft = _to_int(p.lookbackLeft, 5)
        p.lookbackRight = _to_int(p.lookbackRight, 5)
        p.rangeUpper = _to_int(p.rangeUpper, 60)
        p.rangeLower = _to_int(p.rangeLower, 5)
        p.max_wait_bars = _to_int(p.max_wait_bars, 25)
        p.cooldownBars = _to_int(p.cooldownBars, 15)
        p.use_pct_stop = _to_float(p.use_pct_stop, 0.018)
        p.initial_capital = _to_float(p.initial_capital, 10000.0)
        p.percent_risk = _to_float(p.percent_risk, 0.10)
        # experimental lock profit params disabled
        p.lock_arm_pct = 0.0
        p.lock_profit_pct = 0.0
        if isinstance(p.enableHTFGate, str):
            p.enableHTFGate = p.enableHTFGate.lower() == 'true'
        p.htf_pct_stop = _to_float(p.htf_pct_stop, 0.20)
        p.htf_rsi_length = _to_int(p.htf_rsi_length, 14)
        p.htf_rsi_overbought = _to_int(p.htf_rsi_overbought, 79)
        p.htf_rsi_oversold = _to_int(p.htf_rsi_oversold, 27)
        p.htf_lookbackLeft = _to_int(p.htf_lookbackLeft, 5)
        p.htf_lookbackRight = _to_int(p.htf_lookbackRight, 5)
        p.htf_rangeUpper = _to_int(p.htf_rangeUpper, 60)
        p.htf_rangeLower = _to_int(p.htf_rangeLower, 5)
        p.htf_max_wait_bars = _to_int(p.htf_max_wait_bars, 25)
        self.p = p
    def _compute_series(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        rsi = rsi_wilder(df["close"], self.p.rsi_length)
        return {"rsi": rsi}

    def _crossover(self, s: pd.Series, level: float) -> pd.Series:
        prev = s.shift(1)
        return (prev <= level) & (s > level)

    def _crossunder(self, s: pd.Series, level: float) -> pd.Series:
        prev = s.shift(1)
        return (prev >= level) & (s < level)

    def backtest(self, symbol: str, df: pd.DataFrame) -> Tuple[Dict, List[dict]]:
        if df.empty or len(df) < max(200, self.p.lookbackLeft + self.p.lookbackRight + 20):
            return ({
                "Total Return (%)": 0.0,
                "Num Trades": 0,
                "Win Rate (%)": 0.0,
                "Avg P&L": 0.0,
                "Sharpe": 0.0,
                "Ending Equity": self.p.initial_capital
            }, [])

        ser = self._compute_series(df)
        rsi = ser["rsi"].fillna(50)

        # divergence conditions per bar
        if self.p.calculateDivergence:
            bullCond = bull_divergence(
                rsi, df["low"], self.p.lookbackLeft, self.p.lookbackRight, self.p.rangeLower, self.p.rangeUpper
            )
            bearCond = bear_divergence(
                rsi, df["high"], self.p.lookbackLeft, self.p.lookbackRight, self.p.rangeLower, self.p.rangeUpper
            )
        else:
            bullCond = pd.Series(False, index=df.index)
            bearCond = pd.Series(False, index=df.index)

        # LTF setups
        # Arm long when RSI dips below OS; close setup when RSI OB crossunder
        rsi_below_os = rsi < self.p.rsi_oversold
        # recently_armed series across LTF bars
        _idx = np.arange(len(rsi_below_os), dtype=float)
        _last_true = np.where(rsi_below_os.values, _idx, np.nan)
        _last_true = pd.Series(_last_true, index=df.index).ffill().values
        _bars_since = _idx - np.where(np.isnan(_last_true), np.inf, _last_true)
        recently_armed = pd.Series(_bars_since <= float(self.p.max_wait_bars), index=df.index)
        rsi_setup_bear = self._crossunder(rsi, self.p.rsi_overbought)

        # HTF gate (stateless computation on closed HTF bars, forward-filled to LTF)
        if self.p.enableHTFGate:
            htf = resample_ohlcv(df, self.p.htfTF)
            # Use HTF-specific params if provided
            htf_len = int(self.p.htf_rsi_length)
            htf_ob  = int(self.p.htf_rsi_overbought)
            htf_os  = int(self.p.htf_rsi_oversold)
            htf_lb_l = int(self.p.htf_lookbackLeft)
            htf_lb_r = int(self.p.htf_lookbackRight)
            htf_rng_u = int(self.p.htf_rangeUpper)
            htf_rng_l = int(self.p.htf_rangeLower)
            htf_wait  = int(self.p.htf_max_wait_bars)

            rsi_htf = rsi_wilder(htf["close"], htf_len).fillna(50)
            # Bullish divergence and recently armed on HTF
            bull_htf = bull_divergence(
                rsi_htf, htf["low"], htf_lb_l, htf_lb_r, htf_rng_l, htf_rng_u
            )
            # bars since RSI < OS on HTF
            cond_htf = (rsi_htf < htf_os)
            idx_arr = np.arange(len(cond_htf), dtype=float)
            last_true = np.where(cond_htf.values, idx_arr, np.nan)
            last_true = pd.Series(last_true, index=cond_htf.index).ffill().values
            bars_since_htf = idx_arr - np.where(np.isnan(last_true), np.inf, last_true)
            recently_armed_htf = pd.Series(bars_since_htf <= float(htf_wait), index=cond_htf.index)
            htf_enter_sig = bull_htf & recently_armed_htf
            htf_close_sig = self._crossunder(rsi_htf, htf_ob)

            # Build gateOpen over HTF bars with 20% HTF stop
            gate_vals = []
            gate_open = True
            htf_entry_price = np.nan
            htf_stop_price = np.nan
            for i in range(len(htf)):
                # apply SL if armed
                if gate_open and not np.isnan(htf_stop_price):
                    if float(htf["low"].iloc[i]) <= float(htf_stop_price):
                        gate_open = False
                        htf_entry_price = np.nan
                        htf_stop_price = np.nan
                # signals on this closed HTF bar
                if bool(htf_close_sig.iloc[i]):
                    gate_open = False
                    htf_entry_price = np.nan
                    htf_stop_price = np.nan
                if bool(htf_enter_sig.iloc[i]):
                    gate_open = True
                    htf_entry_price = float(htf["close"].iloc[i])
                    htf_stop_price = htf_entry_price * (1.0 - float(self.p.htf_pct_stop))
                gate_vals.append(gate_open)
            gate_htf = pd.Series(gate_vals, index=htf.index)
            gate_ltf = gate_htf.reindex(df.index, method="ffill").fillna(True)
        else:
            gate_ltf = pd.Series(True, index=df.index)

        # We'll use stateless "recently armed" instead of stateful arming for long entries
        awaiting_div_bear = False
        awaiting_bars_bear = 0
        in_pos = False
        entry = np.nan
        stop = np.nan
        qty = 0.0
        last_stop = np.nan
        inCooldown = False
        cdBarsLeft = 0
        m_tick = mintick(symbol)
        runup_peak = 0.0
        equity = float(self.p.initial_capital)
        eq_curve = [equity]
        fee_factor = self.p.fee_bps / 10_000.0

        trades: List[dict] = []

        # Helpful shifted series for Pine-like wave_low at pivot
        lowR = df["low"].shift(self.p.lookbackRight)
        highR = df["high"].shift(self.p.lookbackRight)

        for i in range(len(df)):
            t = df.index[i]
            price = float(df["close"].iloc[i])
            r = float(rsi.iloc[i])

            # setups
            if in_pos and bool(rsi_setup_bear.iloc[i]):
                awaiting_div_bear = True
                awaiting_bars_bear = 0
            if awaiting_div_bear:
                awaiting_bars_bear += 1
                if awaiting_bars_bear > self.p.max_wait_bars:
                    awaiting_div_bear = False
                    awaiting_bars_bear = 0

            # entry
            # recentlyArmed: bars since RSI dipped below OS <= max_wait_bars
            # Precompute outside the loop for efficiency
            # (computed below once, reused here via closure)
            entry_condition_raw = (not in_pos) and bool(bullCond.iloc[i]) and bool(recently_armed.iloc[i])
            # Gate must be open (forward-filled HTF state) and not in cooldown
            canEnter = (not inCooldown) and bool(gate_ltf.iloc[i])
            if entry_condition_raw and canEnter:
                # stop candidate: min(last wave low (price) at pivot, pct stop)
                wave_low = float(valuewhen(bullCond, lowR, 0).iloc[i]) if not np.isnan(valuewhen(bullCond, lowR, 0).iloc[i]) else np.nan
                entry_price = price
                pct_stop_price = entry_price * (1 - self.p.use_pct_stop)
                stop_price = pct_stop_price
                if not np.isnan(wave_low):
                    stop_price = min(wave_low, pct_stop_price)
                if stop_price >= entry_price:
                    stop_price = pct_stop_price
                min_stop_dist = m_tick * 3.0
                min_allowed = entry_price - min_stop_dist
                if stop_price > min_allowed:
                    stop_price = min_allowed

                # sizing: percent of equity notionally
                risk_val = equity * self.p.percent_risk
                qty = max(0.0, risk_val / max(1e-9, entry_price))
                fee = entry_price * qty * fee_factor
                equity -= fee

                in_pos = True
                entry = entry_price
                stop = stop_price
                last_stop = stop
                runup_peak = 0.0
                trades.append({"symbol": symbol, "t": t.isoformat(), "type": "enter", "price": entry_price, "qty": qty, "stop": stop_price})

            # exits: normal via bear divergence after OB setup
            if in_pos and awaiting_div_bear and bool(bearCond.iloc[i]):
                exit_price = price
                pnl = (exit_price - entry) * qty
                fee = exit_price * qty * fee_factor
                pnl -= fee
                equity += pnl
                trades.append({"symbol": symbol, "t": t.isoformat(), "type": "exit_normal", "price": exit_price, "qty": qty, "pnl": pnl})
                in_pos = False
                awaiting_div_bear = False
                awaiting_bars_bear = 0
                last_stop = np.nan
                eq_curve.append(equity)

            # stop loss
            if in_pos and float(df["low"].iloc[i]) <= stop:
                exit_price = stop
                pnl = (exit_price - entry) * qty
                fee = exit_price * qty * fee_factor
                pnl -= fee
                equity += pnl
                trades.append({"symbol": symbol, "t": t.isoformat(), "type": "exit_sl", "price": exit_price, "qty": qty, "pnl": pnl})
                in_pos = False
                cdBarsLeft = self.p.cooldownBars
                inCooldown = cdBarsLeft > 0
                eq_curve.append(equity)

            # experimental: lock profit stop after runup >= arm
            if in_pos:
                # update runup peak
                try:
                    ru = (price / entry - 1.0) * 100.0
                except Exception:
                    ru = 0.0
                runup_peak = max(runup_peak, ru)
                if (self.p.lock_arm_pct > 0) and (self.p.lock_profit_pct > 0) and (runup_peak >= self.p.lock_arm_pct):
                    lock_st = entry * (1 + self.p.lock_profit_pct/100.0)
                    if lock_st > price:
                        lock_st = price
                    stop = max(stop, lock_st)

            # cooldown tick
            if inCooldown and not in_pos:
                # approximate bar confirmation by counting each iteration
                cdBarsLeft = max(cdBarsLeft - 1, 0)
                if cdBarsLeft == 0:
                    inCooldown = False

        # metrics
        df_tr = pd.DataFrame(trades)
        if df_tr.empty:
            metrics = {
                "Total Return (%)": 0.0,
                "Num Trades": 0,
                "Win Rate (%)": 0.0,
                "Avg P&L": 0.0,
                "Sharpe": 0.0,
                "Max Drawdown (%)": 0.0,
                "Ending Equity": round(equity, 2)
            }
        else:
            exits = df_tr[df_tr["type"].str.startswith("exit")]
            pnl = exits["pnl"] if not exits.empty else pd.Series(dtype=float)
            total_return = (equity / self.p.initial_capital - 1.0) * 100.0
            winrate = float((pnl > 0).mean() * 100) if not pnl.empty else 0.0
            avg_pnl = float(pnl.mean()) if not pnl.empty else 0.0
            sd = float(np.nanstd(pnl.to_numpy(), ddof=1)) if len(pnl) > 1 else 0.0
            sharpe = (avg_pnl / sd * np.sqrt(252)) if sd > 0 else 0.0
            # max drawdown on closed-trade equity
            eq = pd.Series(eq_curve if eq_curve else [self.p.initial_capital], dtype=float)
            peak = eq.cummax()
            dd = (eq / peak - 1.0) * 100.0
            mdd = float(min(0.0, dd.min()))
            metrics = {
                "Total Return (%)": round(total_return, 2),
                "Num Trades": int((df_tr["type"] == "enter").sum()),
                "Win Rate (%)": round(winrate, 2),
                "Avg P&L": round(avg_pnl, 2),
                "Sharpe": round(sharpe, 2),
                "Max Drawdown (%)": round(mdd, 2),
                "Ending Equity": round(equity, 2)
            }

        return metrics, trades[-500:]

    def signal_snapshot(self, symbol: str, df: pd.DataFrame) -> Dict:
        # compute back to generate events; then return last state + compact chart payload
        metrics, trades = self.backtest(symbol, df)
        # build chart payload
        candles = [
            {
                "t": idx.isoformat(),
                "o": float(row["open"]),
                "h": float(row["high"]),
                "l": float(row["low"]),
                "c": float(row["close"]),
            }
            for idx, row in df.tail(500).iterrows()
        ]
        markers = [
            {"t": tr.get("t"), "type": tr["type"], "price": tr.get("price")}
            for tr in trades if tr.get("t") is not None
        ]
        last = trades[-1] if trades else None
        action = "HOLD"
        if last:
            if last["type"] == "enter":
                action = "BUY"
            elif last["type"].startswith("exit"):
                action = "SELL"
        snapshot = {
            "symbol": symbol,
            "action": action,
            "metrics": metrics,
            "trades": trades,
            "chart": {"candles": candles, "markers": markers[-200:]},
        }
        return snapshot




