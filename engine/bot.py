import os, math, logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, List

from .data import ensure_dt, resample_ohlcv, fetch_ccxt_hist, fetch_ccxt_hist_range, synthetic_hourly, mintick
from .indicators import rsi_wilder
from .divergence import bull_divergence, bear_divergence, valuewhen
from .filters import dxy_ok, htf_bias, mid_chop, bb_squeeze
from .executor import Executor3M

log = logging.getLogger("engine-bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

class RemixBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.symbols = cfg["symbols"]
        self.capital = float(cfg["initial_capital"])
        self.equity = self.capital
        self.fee_bps = float(cfg["fee_bps"])
        self.cache: Dict[str, pd.DataFrame] = {}
        self.used_synthetic = False
        self.execs: Dict[str, Executor3M] = {
            s: Executor3M(cfg["rsi_oversold"], cfg["rsi_overbought"], cfg["max_wait_bars"], cfg["cooldown_3m_bars"])
            for s in self.symbols
        }
        self.trades: List[dict] = []

    def load_hist(self, symbol: str) -> pd.DataFrame:
        try:
            # Prefer full-range fetch if possible
            df = fetch_ccxt_hist_range(symbol, timeframe=self.cfg["timeframe_hist"],
                                       start=self.cfg["backtest_start"], end=self.cfg["backtest_end"])
            if df.empty:
                # fallback to single-shot
                df = fetch_ccxt_hist(symbol, timeframe=self.cfg["timeframe_hist"])            
        except Exception as e:
            if self.cfg.get("use_synthetic_if_ccxt_fails", True):
                log.warning(f"CCXT failed for {symbol}: {e}. Using synthetic.")
                seed = self.cfg.get("synthetic_seed")
                df = synthetic_hourly(self.cfg["backtest_start"], self.cfg["backtest_end"], seed=seed)
                self.used_synthetic = True
            else:
                raise
        df = df[(df.index>=self.cfg["backtest_start"]) & (df.index<=self.cfg["backtest_end"])]
        self.cache[symbol] = ensure_dt(df.copy())
        return self.cache[symbol]

    # Removed ML and external risk engine; stops will be computed Pine-style at entry

    def run_backtest(self):
        if self.cfg["use_dxy_filter"] and not dxy_ok(self.cfg["dxy_wow_threshold"], True):
            log.info("DXY filter: skipping period due to USD volatility.")
            return

        for symbol in self.symbols:
            dfh = self.load_hist(symbol)
            if len(dfh) < 400:
                log.info(f"{symbol}: not enough history"); continue
            m3 = resample_ohlcv(dfh, "3m")
            if len(m3) < 500:
                log.info(f"{symbol}: insufficient 3m candles"); continue

            # Build HTF gate on 30m (stateless), forward-fill to LTF (3m)
            try:
                htf_tf = "30m"
                htf = resample_ohlcv(dfh, htf_tf)
                rsi_len = self.cfg["rsi_length"]; lb_left=self.cfg["lb_left"]; lb_right=self.cfg["lb_right"]
                range_low=self.cfg["range_low"]; range_up=self.cfg["range_up"]
                rsi_htf = rsi_wilder(htf["close"], rsi_len).fillna(50)
                bull_htf = bull_divergence(rsi_htf, htf["low"], lb_left, lb_right, range_low, range_up)
                cond_htf = (rsi_htf < self.cfg["rsi_oversold"])            
                idx = np.arange(len(htf), dtype=float)
                last_true = np.where(cond_htf.values, idx, np.nan)
                last_true = pd.Series(last_true, index=htf.index).ffill().values
                bars_since = idx - np.where(np.isnan(last_true), np.inf, last_true)
                recently_armed_htf = pd.Series(bars_since <= float(self.cfg["max_wait_bars"]), index=htf.index)
                prev = rsi_htf.shift(1)
                htf_close_sig = (prev >= self.cfg["rsi_overbought"]) & (rsi_htf < self.cfg["rsi_overbought"])  # crossunder
                htf_enter_sig = bull_htf & recently_armed_htf
                # Gate with HTF 20% stop
                gate_vals = []
                gate_open = True
                htf_entry_price = np.nan
                htf_stop_price = np.nan
                for j in range(len(htf)):
                    if gate_open and not np.isnan(htf_stop_price):
                        if float(htf["low"].iloc[j]) <= float(htf_stop_price):
                            gate_open = False
                            htf_entry_price = np.nan
                            htf_stop_price = np.nan
                    if bool(htf_close_sig.iloc[j]):
                        gate_open = False
                        htf_entry_price = np.nan
                        htf_stop_price = np.nan
                    if bool(htf_enter_sig.iloc[j]):
                        gate_open = True
                        htf_entry_price = float(htf["close"].iloc[j])
                        htf_stop_price = htf_entry_price * (1.0 - 0.20)
                    gate_vals.append(gate_open)
                gate_htf = pd.Series(gate_vals, index=htf.index)
                gate_ltf = gate_htf.reindex(m3.index, method="ffill").fillna(True)
            except Exception:
                gate_ltf = pd.Series(True, index=m3.index)

            for i in range(max(400, self.cfg["lb_left"]+self.cfg["lb_right"]+60), len(m3)):
                m3_slice = m3.iloc[:i+1]
                last = m3_slice.iloc[-1]
                df = dfh[dfh.index <= last.name]

                # Prefilter: BB squeeze on 1h
                if not bb_squeeze(resample_ohlcv(df, "1h"), self.cfg["bb_period"], self.cfg["bb_std"]):
                    continue

                # Engines
                bias, bias_conf = htf_bias(df, self.cfg["ema_short"], self.cfg["ema_long"])
                trad, trad_conf = mid_chop(df, self.cfg["chop_length"])

                # Divergences on 3m
                rsi3 = rsi_wilder(m3_slice["close"], self.cfg["rsi_length"])
                bull = bull_divergence(rsi3, m3_slice["low"],
                                       self.cfg["lb_left"], self.cfg["lb_right"],
                                       self.cfg["range_low"], self.cfg["range_up"]).iloc[-1]
                bear = bear_divergence(rsi3, m3_slice["high"],
                                       self.cfg["lb_left"], self.cfg["lb_right"],
                                       self.cfg["range_low"], self.cfg["range_up"]).iloc[-1]

                # Sizing: percent-of-equity notionally (align with Pine default_qty_type/value)
                C = 0.5
                def size_fn(equity, entry, stop, conf_for_sizing):
                    pct = float(self.cfg.get("base_risk_pct", 0.01))
                    qty = 0.0 if entry <= 0 else (equity * pct) / float(entry)
                    return float(max(0.0, qty)), pct

                # Pine-style stop candidate at this bar: min(last wave low at bull pivot, pct stop)
                rsi3_full = rsi_wilder(m3["close"].iloc[:i+1], self.cfg["rsi_length"])
                bull_series = bull_divergence(rsi3_full, m3["low"].iloc[:i+1],
                                              self.cfg["lb_left"], self.cfg["lb_right"],
                                              self.cfg["range_low"], self.cfg["range_up"])
                lowR = m3["low"].iloc[:i+1].shift(self.cfg["lb_right"])
                try:
                    wave_low = float(valuewhen(bull_series, lowR, 0).iloc[-1])
                except Exception:
                    wave_low = float('nan')
                entry_price = float(last["close"])
                pct_stop_price = entry_price * (1 - float(self.cfg["pct_stop"]))
                stop_cand = pct_stop_price if np.isnan(wave_low) else min(wave_low, pct_stop_price)
                min_allowed = entry_price - 3.0*mintick(symbol)
                if stop_cand > min_allowed:
                    stop_cand = min_allowed

                evt = self.execs[symbol].on_bar(
                    symbol=symbol,
                    bar_high=float(last["high"]),
                    bar_low=float(last["low"]),
                    bar_close=float(last["close"]),
                    rsi=float(rsi3.iloc[-1]),
                    bullCond=bool(bull),
                    bearCond=bool(bear),
                    bias=bias,
                    trad=trad,
                    conf_for_sizing=C,
                    div_score=(1.0 if bool(bull) else 0.0),
                    stop_candidate=float(stop_cand),
                    equity=self.equity,
                    size_fn=size_fn,
                    gate_open=bool(gate_ltf.iloc[i])
                )

                if evt:
                    if evt["type"] == "enter_long":
                        fee = evt["entry"]*evt["qty"]*(self.fee_bps/10_000)
                        self.equity -= fee
                        self.trades.append({"symbol":symbol, "t":last.name, "type":"enter", "price":evt["entry"], "qty":evt["qty"]})
                        log.info(f"{symbol} ENTER long @{evt['entry']:.2f} stop {evt['stop']:.2f} qty {evt['qty']:.4f} (risk {evt['risk_pct']*100:.2f}%)")

                    elif evt["type"] in ("exit_normal","exit_sl"):
                        # find last open pos qty (stored in trades list)
                        qty = next((x["qty"] for x in reversed(self.trades) if x["symbol"]==symbol and x["type"]=="enter"), 0.0)
                        exit_p = evt["exit"]
                        pnl = (exit_p - evt["entry"]) * qty
                        fee = exit_p*qty*(self.fee_bps/10_000)
                        pnl -= fee
                        self.equity += pnl
                        self.trades.append({"symbol":symbol, "t":last.name, "type":evt["type"], "price":exit_p, "qty":qty, "pnl":pnl})
                        log.info(f"{symbol} EXIT {evt['type']} @{exit_p:.2f} PnL {pnl:.2f} | equity {self.equity:.2f}")

        return self.report()

    def report(self):
        df = pd.DataFrame(self.trades)
        if df.empty:
            return {
                "Total Return (%)": 0.0,
                "Num Trades": 0,
                "Win Rate (%)": 0.0,
                "Avg P&L": 0.0,
                "Sharpe": 0.0,
                "Ending Equity": self.equity,
                "Synthetic Data Used": bool(self.used_synthetic),
            }
        pnl = df[df["type"].str.startswith("exit")]["pnl"]
        total_return = (self.equity/float(self.capital) - 1.0)*100
        winrate = float((pnl>0).mean()*100) if not pnl.empty else 0.0
        avg_pnl = float(pnl.mean()) if not pnl.empty else 0.0
        sd = float(np.nanstd(pnl.to_numpy(), ddof=1)) if len(pnl) > 1 else 0.0
        sharpe = (avg_pnl/sd*math.sqrt(252)) if sd>0 else 0.0
        return {
            "Total Return (%)": round(total_return,2),
            "Num Trades": int((df["type"]=="enter").sum()),
            "Win Rate (%)": round(winrate,2),
            "Avg P&L": round(avg_pnl,2),
            "Sharpe": round(sharpe,2),
            "Ending Equity": round(self.equity,2),
            "Synthetic Data Used": bool(self.used_synthetic),
        }
