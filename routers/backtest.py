from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from engine.pine_long import PineLongEngine
from engine.storage import get_ohlcv
from experiment.concurrent_backtester import ConcurrentBacktestConfig, run_concurrent_backtest
from schemas.backtest import BacktestReq, ConcurrentBacktestRequest, DeepBacktestRequest
from utils.dates import norm_date
from utils.symbols import norm_symbol

router = APIRouter(tags=["backtest"])


def _candles_from_df(xdf):
    return [
        {"t": idx.isoformat(), "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]), "c": float(r["close"])}
        for idx, r in xdf.iterrows()
    ]


@router.post("/backtest")
def backtest(req: BacktestReq):
    try:
        symbol = norm_symbol(req.symbols[0])
        start = norm_date(req.start)
        end = norm_date(req.end)
        timeframe = req.overrides.get("timeframe_hist", "3m")
        pine_params = {k: v for k, v in req.overrides.items() if k not in ("timeframe_hist",)}
        df = get_ohlcv(symbol, timeframe, start, end)

        if req.engine == "both":
            from engine.hedge import backtest_hedged

            # Derive init_stop_pct robustly: prefer explicit init_stop_pct (percent),
            # fall back to use_pct_stop (fraction) if provided, else default 5.
            _init_stop_pct = pine_params.get("init_stop_pct", None)
            if _init_stop_pct is None:
                try:
                    ups = pine_params.get("use_pct_stop", None)
                    if ups is not None:
                        _init_stop_pct = float(ups) * 100.0
                except Exception:
                    _init_stop_pct = None
            if _init_stop_pct is None:
                _init_stop_pct = 5.0

            hedge_params = {
                "rsi_length": pine_params.get("rsi_length", 14),
                "rsi_overbought": pine_params.get("rsi_overbought", 79),
                "rsi_oversold": pine_params.get("rsi_oversold", 27),
                "lookbackLeft": pine_params.get("lookbackLeft", 5),
                "lookbackRight": pine_params.get("lookbackRight", 5),
                "rangeUpper": pine_params.get("rangeUpper", 60),
                "rangeLower": pine_params.get("rangeLower", 5),
                "initial_capital": pine_params.get("initial_capital", 10000.0),
                "size_equity_pct": pine_params.get("size_equity_pct", 0.50),
                "fee_bps": pine_params.get("fee_bps", 5.0),
                "init_stop_pct": _init_stop_pct,
                "trail_start_pct": pine_params.get("trail_start_pct", 1.0),
                "trail_bump_pct": pine_params.get("trail_bump_pct", 2.0),
                "trail_step_pct": pine_params.get("trail_step_pct", 5.0),
                "tp_half_pct": pine_params.get("tp_half_pct", 7.0),
                "allow_stop_above_entry": pine_params.get("allow_stop_above_entry", True),
                "cooldown_bars": pine_params.get("cooldownBars", 0),
                # experimental profit-lock removed
            }
            metrics, trades, eq, eqL, eqS = backtest_hedged(symbol, df, hedge_params)
            # Diagnostics: log any negative prices before sanitization to trace root cause
            try:
                suspects = []
                for _t in trades:
                    pr = _t.get("price")
                    stp = _t.get("stop")
                    if pr is not None:
                        try:
                            if float(pr) < 0:
                                suspects.append({k: _t.get(k) for k in ("t", "side", "type", "price", "qty", "pnl", "stop")})
                        except Exception:
                            pass
                    if stp is not None:
                        try:
                            if float(stp) < 0:
                                if _t not in suspects:
                                    suspects.append({k: _t.get(k) for k in ("t", "side", "type", "price", "qty", "pnl", "stop")})
                        except Exception:
                            pass
                if suspects:
                    from datetime import datetime as _dt

                    with open("server.err.log", "a", encoding="utf-8") as _logf:
                        _logf.write(
                            f"[DEBUG backtest hedge] {symbol} {start}->{end} tf={timeframe} NEGATIVE entries at {_dt.utcnow().isoformat()}Z: {suspects}\n"
                        )
            except Exception:
                pass
            # Sanitize any negative prices (visual/logging only)
            for _t in trades:
                try:
                    if float(_t.get("price", 0)) < 0:
                        _t["price"] = abs(float(_t.get("price")))
                except Exception:
                    pass
            candles = _candles_from_df(df)
            markers = [
                {
                    "t": t.get("t"),
                    "price": (abs(float(t.get("price", 0))) if (t.get("price") is not None) else None),
                    "type": t.get("type"),
                    "side": t.get("side"),
                }
                for t in trades
                if t.get("type") in ("enter", "exit_sl", "exit_trail", "exit_half_tp", "exit_normal")
            ]
            equity_series = [{"t": ts.isoformat(), "equity": float(val)} for ts, val in eq]
            equity_series_long = [{"t": ts.isoformat(), "equity": float(val)} for ts, val in eqL]
            equity_series_short = [{"t": ts.isoformat(), "equity": float(val)} for ts, val in eqS]
            # Optional debug field (non-breaking) to surface any negative price trades that slipped through
            dbg = []
            try:
                for _t in trades:
                    try:
                        if _t.get("price") is not None and float(_t.get("price")) < 0:
                            dbg.append({k: _t.get(k) for k in ("t", "side", "type", "price", "qty", "pnl", "stop")})
                    except Exception:
                        pass
            except Exception:
                pass
            return {
                "metrics": metrics,
                "trades": trades,
                "candles": candles,
                "markers": markers,
                "equity_series": equity_series,
                "equity_series_long": equity_series_long,
                "equity_series_short": equity_series_short,
                "debug_negatives": dbg,
                "used_params": {"init_stop_pct": hedge_params.get("init_stop_pct")},
            }
        else:
            if req.engine == "short":
                from engine.pine_short import PineShortEngine as Engine
            else:
                Engine = PineLongEngine
            eng = Engine(pine_params)
            metrics, trades = eng.backtest(symbol, df)
            candles = _candles_from_df(df)
            markers = [
                {"t": t.get("t"), "price": t.get("price"), "type": t.get("type"), "side": (req.engine or "long")}
                for t in trades
                if t.get("type") in ("enter", "exit_sl", "exit_normal")
            ]
            # build equity from realized PnL
            eq = []
            equity = float(pine_params.get("initial_capital", 10000.0))
            for t in trades:
                if str(t.get("type", "")).startswith("exit"):
                    equity += float(t.get("pnl", 0))
                    from datetime import datetime as _dt

                    try:
                        ts = _dt.fromisoformat(t.get("t").replace("Z", ""))
                    except Exception:
                        ts = None
                    if ts:
                        eq.append({"t": ts.isoformat(), "equity": equity})
            return {"metrics": metrics, "trades": trades, "candles": candles, "markers": markers, "equity_series": eq}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/deep")
def backtest_deep(req: DeepBacktestRequest):
    try:
        symbol = norm_symbol(req.symbol)
        today = datetime.utcnow().date()
        end_raw = req.end or today.isoformat()
        start_raw = req.start or (today - timedelta(days=365 * 3)).isoformat()
        start = norm_date(start_raw)
        end = norm_date(end_raw)
        overrides = dict(req.overrides or {})
        if "timeframe_hist" not in overrides and req.timeframe:
            overrides["timeframe_hist"] = req.timeframe
        bt_req = BacktestReq(
            symbols=[symbol],
            start=start,
            end=end,
            overrides=overrides,
            engine=req.engine or "long",
        )
        return backtest(bt_req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/backtest/concurrent")
def backtest_concurrent(req: ConcurrentBacktestRequest):
    try:
        cfg = ConcurrentBacktestConfig(
            dataset_path=Path(req.dataset_path),
            model_path=Path(req.model_path) if req.model_path else None,
            threshold=req.threshold,
            symbols=req.symbols or None,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_equity=req.initial_equity,
            equity_pct=req.equity_pct,
            fee_bps=req.fee_bps,
            max_positions=req.max_positions,
            max_assets=req.max_assets,
        )
        result = run_concurrent_backtest(cfg)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
