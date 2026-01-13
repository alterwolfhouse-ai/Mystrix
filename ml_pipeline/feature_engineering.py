"""Indicator and feature engineering helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from engine.indicators import atr, rsi_wilder  # noqa: E402


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi_wilder(out["close"], 14)
    out["ema21"] = out["close"].ewm(span=21, adjust=False).mean()
    out["ema55"] = out["close"].ewm(span=55, adjust=False).mean()
    out["mom3"] = out["close"].pct_change(3)
    out["mom10"] = out["close"].pct_change(10)
    out["vol_ratio"] = out["volume"] / out["volume"].rolling(20).mean()
    out["atr"] = atr(out, length=14)
    out["pullback20"] = out["close"] / out["high"].rolling(20).max() - 1
    out["hh20"] = out["high"].rolling(20).max()
    out["ll20"] = out["low"].rolling(20).min()
    return out


def base_features(df: pd.DataFrame, ts: pd.Timestamp, direction: int, symbol: str) -> dict:
    price = df.at[ts, "close"]
    get = lambda col, default=0.0: float(df.at[ts, col]) if col in df.columns and pd.notna(df.at[ts, col]) else default
    return {
        "rsi": get("rsi"),
        "price_vs_ema21": float(price / get("ema21", price) - 1.0),
        "price_vs_ema55": float(price / get("ema55", price) - 1.0),
        "mom3": get("mom3"),
        "mom10": get("mom10"),
        "vol_ratio": get("vol_ratio"),
        "atr_pct": float(df.at[ts, "atr"] / price),
        "pullback20": get("pullback20"),
        "direction": direction,
        "symbol": symbol,
        "entry_hour": ts.hour,
        "entry_day": ts.dayofweek,
        "htf_rsi": get("htf_rsi"),
        "htf_ema21": get("htf_ema21"),
        "htf_ema55": get("htf_ema55"),
        "htf_trend_slope": get("htf_trend_slope"),
        "htf_trend_strength": get("htf_trend_strength"),
        "htf_trend_dir": get("htf_trend_dir"),
        "htf_rsi_regime": get("htf_rsi_regime"),
        "sr_proximity": get("sr_proximity"),
        "range_context": get("range_context"),
    }
