import os
import time
import threading
import numpy as np
import pandas as pd
from typing import Optional

try:
    import ccxt
except Exception:
    ccxt = None

_EXCHANGE = None
_EXCHANGE_LOCK = threading.Lock()


def _get_exchange():
    global _EXCHANGE
    if ccxt is None:
        raise RuntimeError("ccxt not installed")
    if _EXCHANGE is None:
        with _EXCHANGE_LOCK:
            if _EXCHANGE is None:
                ex = ccxt.binance({"enableRateLimit": True})
                try:
                    ex.load_markets()
                except Exception:
                    # best effort; avoid hard failure on startup
                    pass
                _EXCHANGE = ex
    return _EXCHANGE

def ensure_dt(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df

def resample_ohlcv(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    # Use modern frequency aliases to avoid deprecation warnings
    rulemap = {
        "1w": "W",
        "1d": "D",
        "4h": "4h",
        "1h": "1h",
        "30m": "30min",
        "15m": "15min",
        "5m": "5min",
        "3m": "3min",
    }
    rule = rulemap.get(tf, "H")
    agg = {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    return df.resample(rule).agg(agg).dropna()

def fetch_ccxt_hist(symbol: str, timeframe="1h", since_ms: Optional[int]=None) -> pd.DataFrame:
    if ccxt is None:
        raise RuntimeError("ccxt not installed")
    ex = ccxt.binance()
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=1000)
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df.astype(float)

def fetch_ccxt_hist_range(symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV across a custom time range by paging exchange API.
    Returns DataFrame indexed by timestamp with columns open, high, low, close, volume.
    """
    if ccxt is None:
        raise RuntimeError("ccxt not installed")
    ex = ccxt.binance({"enableRateLimit": True})
    start_dt = pd.to_datetime(start, dayfirst=True)
    end_dt = pd.to_datetime(end, dayfirst=True)
    since = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    all_rows = []
    limit = 1000
    while True:
        data = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        if not data:
            break
        all_rows.extend(data)
        last_ts = data[-1][0]
        # advance by one interval to avoid duplicates
        if last_ts >= end_ms:
            break
        since = last_ts + 1
        # be polite to API
        time.sleep(getattr(ex, 'rateLimit', 200) / 1000)
        # safety cap to prevent infinite loops
        if len(all_rows) > 1_000_000:
            break
    if not all_rows:
        return pd.DataFrame(columns=["open","high","low","close","volume"], index=pd.to_datetime([]))
    df = pd.DataFrame(all_rows, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    # clip to requested range strictly
    return df[(df.index >= start_dt) & (df.index <= end_dt)]

def fetch_ccxt_recent(symbol: str, timeframe: str = "3m", limit: int = 2000) -> pd.DataFrame:
    ex = _get_exchange()
    try:
        data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception:
        # reset exchange and retry once
        with _EXCHANGE_LOCK:
            global _EXCHANGE
            _EXCHANGE = None
        ex = _get_exchange()
        data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not data:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.to_datetime([]))
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.astype(float)

def synthetic_hourly(start: str, end: str, seed: Optional[int] = None) -> pd.DataFrame:
    start = pd.to_datetime(start); end = pd.to_datetime(end)
    periods = int((end-start).total_seconds() // 3600) + 1
    idx = pd.date_range(start, periods=periods, freq="H")
    if seed is None:
        seed_env = os.environ.get("SYNTHETIC_SEED")
        if seed_env not in (None, ""):
            try:
                seed = int(seed_env)
            except Exception:
                seed = None
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.00015, 0.018, periods)
    close = 20000 * np.exp(np.cumsum(rets))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, periods)))
    low  = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, periods)))
    vol  = rng.lognormal(15, 1, periods)
    df = pd.DataFrame({"open":open_,"high":high,"low":low,"close":close,"volume":vol}, index=idx)
    return df

def mintick(symbol: str) -> float:
    try:
        ex = _get_exchange()
        market = None
        try:
            market = ex.market(symbol)
        except Exception:
            try:
                ex.load_markets()
                market = ex.market(symbol)
            except Exception:
                market = None
        if market:
            info = market.get("info", {})
            for key in ("tickSize", "tick_size", "minPrice", "min_price"):
                if key in info:
                    try:
                        return float(info[key])
                    except Exception:
                        pass
            precision = (market.get("precision") or {}).get("price")
            if precision is not None:
                try:
                    return 10 ** (-int(precision))
                except Exception:
                    try:
                        return 10 ** (-float(precision))
                    except Exception:
                        pass
            limits = (market.get("limits") or {}).get("price") or {}
            if limits.get("min") is not None:
                try:
                    return float(limits["min"])
                except Exception:
                    pass
    except Exception:
        pass
    return 0.01
