from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

try:
    import ccxt
except Exception:
    ccxt = None

from engine.data import fetch_ccxt_recent
from engine.indicators import rsi_wilder
from engine.pine_long import PineLongEngine
from engine.storage import get_recent
from utils.symbols import norm_symbol


router = APIRouter(tags=["pine"])


@router.get("/pine/signal")
def pine_signal(
    symbol: str = "BTC/USDT",
    timeframe: str = "3m",
    bars: int = 500,
    rsi_length: int | None = None,
    rsi_overbought: int | None = None,
    rsi_oversold: int | None = None,
    lookbackLeft: int | None = None,
    lookbackRight: int | None = None,
    rangeLower: int | None = None,
    rangeUpper: int | None = None,
    use_pct_stop: float | None = None,
    max_wait_bars: int | None = None,
    cooldownBars: int | None = None,
    initial_capital: float | None = None,
    percent_risk: float | None = None,
):
    try:
        sym = norm_symbol(symbol)
        # Prefer live recent fetch from CCXT for correct latest price; fall back to cache
        try:
            df = fetch_ccxt_recent(sym, timeframe=timeframe, limit=min(max(100, bars), 5000))
        except Exception:
            df = get_recent(sym, timeframe=timeframe, bars=bars)
        pine_params: Dict[str, Any] = {}
        for k, v in dict(
            rsi_length=rsi_length,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
            lookbackLeft=lookbackLeft,
            lookbackRight=lookbackRight,
            rangeLower=rangeLower,
            rangeUpper=rangeUpper,
            use_pct_stop=use_pct_stop,
            max_wait_bars=max_wait_bars,
            cooldownBars=cooldownBars,
            initial_capital=initial_capital,
            percent_risk=percent_risk,
        ).items():
            if v is not None:
                pine_params[k] = v
        eng = PineLongEngine(pine_params or None)
        snap = eng.signal_snapshot(sym, df)
        # If possible, override last price with live ticker
        if ccxt is not None:
            try:
                ex = ccxt.binance()
                tkr = ex.fetch_ticker(sym)
                if isinstance(snap.get("chart"), dict) and snap["chart"].get("candles"):
                    snap["chart"]["candles"][-1]["c"] = float(tkr.get("last", snap["chart"]["candles"][-1]["c"]))
            except Exception:
                pass
        return snap
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
def signals(
    symbols: str = "BTC/USDT",
    timeframe: str = "3m",
    bars: int = 500,
    rsi_length: int | None = None,
    rsi_overbought: int | None = None,
    rsi_oversold: int | None = None,
    lookbackLeft: int | None = None,
    lookbackRight: int | None = None,
    rangeLower: int | None = None,
    rangeUpper: int | None = None,
    use_pct_stop: float | None = None,
    max_wait_bars: int | None = None,
    cooldownBars: int | None = None,
    initial_capital: float | None = None,
    percent_risk: float | None = None,
):
    """Compatibility endpoint for the existing Live Signals UI.
    Uses the Pine engine to compute a simple action snapshot per symbol.
    """
    out = []
    logs: Dict[str, list] = {}
    for sym in [s.strip() for s in symbols.split(",") if s.strip()]:
        try:
            sy = norm_symbol(sym)
            try:
                df = fetch_ccxt_recent(sy, timeframe=timeframe, limit=min(max(100, bars), 5000))
            except Exception:
                df = get_recent(sy, timeframe=timeframe, bars=bars)
            if df.empty:
                out.append({"symbol": sy, "error": "insufficient data"})
                continue
            pine_params: Dict[str, Any] = {}
            for k, v in dict(
                rsi_length=rsi_length,
                rsi_overbought=rsi_overbought,
                rsi_oversold=rsi_oversold,
                lookbackLeft=lookbackLeft,
                lookbackRight=lookbackRight,
                rangeLower=rangeLower,
                rangeUpper=rangeUpper,
                use_pct_stop=use_pct_stop,
                max_wait_bars=max_wait_bars,
                cooldownBars=cooldownBars,
                initial_capital=initial_capital,
                percent_risk=percent_risk,
            ).items():
                if v is not None:
                    pine_params[k] = v
            eng = PineLongEngine(pine_params or None)
            metrics, trades = eng.backtest(sy, df)
            price = float(df["close"].iloc[-1])
            if ccxt is not None:
                try:
                    ex = ccxt.binance()
                    tkr = ex.fetch_ticker(sy)
                    price = float(tkr.get("last", price))
                except Exception:
                    pass
            rsi_last = float(rsi_wilder(df["close"], eng.p.rsi_length).iloc[-1])
            action = "HOLD"
            if trades:
                last = trades[-1]
                if last["type"] == "enter":
                    action = "BUY"
                elif str(last["type"]).startswith("exit"):
                    action = "SELL"
            snap = {"symbol": sy, "price": price, "rsi": rsi_last, "signal": {"action": action}}
            out.append(snap)
            logs[sy] = trades[-5:]
        except Exception as e:
            out.append({"symbol": sym, "error": str(e)})
    return {"signals": out, "logs": logs}


@router.get("/pine/snapshot")
def pine_snapshot(
    symbol: str = "BTC/USDT",
    timeframe: str = "3m",
    bars: int = 500,
    rsi_length: int | None = None,
    rsi_overbought: int | None = None,
    rsi_oversold: int | None = None,
    lookbackLeft: int | None = None,
    lookbackRight: int | None = None,
    rangeLower: int | None = None,
    rangeUpper: int | None = None,
):
    try:
        sy = norm_symbol(symbol)
        try:
            df = fetch_ccxt_recent(sy, timeframe=timeframe, limit=min(max(100, bars), 5000))
        except Exception:
            df = get_recent(sy, timeframe=timeframe, bars=bars)
        if df.empty:
            raise HTTPException(400, "insufficient data")
        pine_params: Dict[str, Any] = {}
        for k, v in dict(
            rsi_length=rsi_length,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
            lookbackLeft=lookbackLeft,
            lookbackRight=lookbackRight,
            rangeLower=rangeLower,
            rangeUpper=rangeUpper,
        ).items():
            if v is not None:
                pine_params[k] = v
        eng = PineLongEngine(pine_params or None)
        snap = eng.signal_snapshot(sy, df)
        return snap
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
