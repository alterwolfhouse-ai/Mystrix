from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd

from engine.storage import raw_ohlcv
from engine.bybit_data import fetch_klines, BYBIT_MAINNET


def get_bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
    sym_raw = symbol.replace("/", "")
    # Prefer RAW
    df = raw_ohlcv(sym_raw, timeframe, int(pd.Timestamp(start).timestamp() * 1000), int(pd.Timestamp(end).timestamp() * 1000))
    if df is None or df.empty:
        # fallback Bybit mainnet
        recent = fetch_klines(sym_raw, timeframe, start_ms=int(pd.Timestamp(start).timestamp() * 1000), end_ms=int(pd.Timestamp(end).timestamp() * 1000), base_url=BYBIT_MAINNET)
        if recent is None or recent.empty:
            return pd.DataFrame(columns=["open","high","low","close","volume"], index=pd.to_datetime([]))
        tmp = recent.copy().rename(columns={"volume_base": "volume"})
        df = tmp[["open", "high", "low", "close", "volume"]]
    else:
        df = df.rename(columns={"volume_base": "volume"})[["open", "high", "low", "close", "volume"]]
    return df


def compute_features(df: pd.DataFrame) -> Dict:
    if df is None or df.empty:
        return {}
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    rsi = _rsi(close, 14)
    macd, macd_signal = _macd(close)
    atr = _atr(df)
    roc = close.pct_change(14) * 100
    feats = {
        "rsi": float(rsi.iloc[-1]) if len(rsi) else None,
        "macd": float(macd.iloc[-1]) if len(macd) else None,
        "macd_signal": float(macd_signal.iloc[-1]) if len(macd_signal) else None,
        "atr_pct": float((atr.iloc[-1] / close.iloc[-1]) * 100) if len(atr) else None,
        "roc14_pct": float(roc.iloc[-1]) if len(roc) else None,
    }
    return feats


def _rsi(series: pd.Series, length: int) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1/length, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = up / (down + 1e-9)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return macd, macd_signal


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = (high - low).abs().combine((high - close).abs(), max).combine((low - close).abs(), max)
    return tr.rolling(length).mean()
