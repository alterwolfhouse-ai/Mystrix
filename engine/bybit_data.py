"""
Bybit v5 market data helpers.

Provides thin wrappers for REST klines with simple normalization and
incremental paging helpers suitable for append‑only storage.

Normalized columns: ts(index, ms), open, high, low, close,
volume_base (Bybit volume), volume_quote (Bybit turnover), is_closed.
"""
from __future__ import annotations

import time
from typing import Optional, List

import httpx
import pandas as pd


BYBIT_TESTNET = "https://api-testnet.bybit.com"
BYBIT_MAINNET = "https://api.bybit.com"


def interval_from_tf(tf: str) -> str:
    tf = tf.lower().strip()
    mapping = {
        "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240", "12h": "720",
        "1d": "D", "1w": "W", "1mo": "M",
    }
    return mapping.get(tf, "60")


def _client(base_url: Optional[str] = None) -> httpx.Client:
    return httpx.Client(base_url=base_url or BYBIT_TESTNET, timeout=30)


def fetch_klines(symbol: str, timeframe: str = "1h", start_ms: Optional[int] = None,
                 end_ms: Optional[int] = None, limit: int = 1000,
                 category: str = "linear", base_url: Optional[str] = None) -> pd.DataFrame:
    try:
        iv = interval_from_tf(timeframe)
        params = {"category": category, "symbol": symbol.replace("/", ""), "interval": iv, "limit": min(max(1, limit), 1000)}
        if start_ms is not None: params["start"] = int(start_ms)
        if end_ms is not None: params["end"] = int(end_ms)
        with _client(base_url) as client:
            r = client.get("/v5/market/kline", params=params)
            r.raise_for_status()
            data = r.json().get("result", {}).get("list", [])
        if not data:
            return _empty_df()
        rows = list(reversed(data))
        df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume","turnover"])
        df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
        df.rename(columns={"volume":"volume_base","turnover":"volume_quote"}, inplace=True)
        df["is_closed"] = 1
        df.set_index("ts", inplace=True)
        return df.astype(float)
    except Exception:
        return _empty_df()


def incremental_fetch(symbol: str, timeframe: str, since_ms: Optional[int], until_ms: Optional[int],
                      overlap_bars: int = 2, base_url: Optional[str] = None) -> pd.DataFrame:
    step_limit = 1000
    out: List[pd.DataFrame] = []
    cur = since_ms
    while True:
        df = fetch_klines(symbol, timeframe, start_ms=cur, end_ms=until_ms, limit=step_limit, base_url=base_url)
        if df.empty:
            break
        out.append(df)
        last_ts = int(df.index[-1].value // 10**6)
        if until_ms is not None and last_ts >= until_ms:
            break
        if len(df) >= 2:
            bar_ms = int((df.index[-1] - df.index[-2]).total_seconds() * 1000)
        else:
            bar_ms = 60_000
        cur = last_ts - overlap_bars * bar_ms
        if since_ms is not None and cur < since_ms:
            cur = since_ms
        time.sleep(0.05)
        if len(out) > 50_000:
            break
    if not out:
        return _empty_df()
    return pd.concat(out).sort_index().astype(float)


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["open","high","low","close","volume_base","volume_quote","is_closed"], index=pd.to_datetime([]))


def fetch_instruments(category: str = "linear", base_url: Optional[str] = None) -> list[str]:
    """Return a list of Bybit symbols (raw, e.g., BTCUSDT) for USDT linear perps currently Trading."""
    try:
        with _client(base_url) as client:
            r = client.get('/v5/market/instruments-info', params={'category': category})
            r.raise_for_status()
            items = r.json().get('result', {}).get('list', []) or []
        syms = []
        for it in items:
            try:
                if (it.get('quoteCoin') == 'USDT') and (str(it.get('status','')).lower() == 'trading'):
                    syms.append(str(it.get('symbol')))
            except Exception:
                continue
        return sorted(syms)
    except Exception:
        return []


def fetch_instruments_all(base_url: Optional[str] = None) -> list[str]:
    """Return USDT instruments from Bybit across linear and spot, paginated."""
    cats = ('linear','spot')
    out = set()
    try:
        for cat in cats:
            cursor = None
            while True:
                params = {'category': cat}
                if cursor:
                    params['cursor'] = cursor
                with _client(base_url) as client:
                    r = client.get('/v5/market/instruments-info', params=params)
                    r.raise_for_status()
                    body = r.json().get('result', {}) or {}
                    items = body.get('list', []) or []
                    cursor = body.get('nextPageCursor') or body.get('nextpagecursor')
                for it in items:
                    try:
                        if str(it.get('quoteCoin')) == 'USDT' and str(it.get('status','')).lower() == 'trading':
                            sym = str(it.get('symbol'))
                            if sym:
                                out.add(sym)
                    except Exception:
                        continue
                if not cursor:
                    break
        return sorted(out)
    except Exception:
        return sorted(out)


def fetch_tickers(category: str = "linear", base_url: Optional[str] = None) -> list[dict]:
    """Return Bybit tickers for a category (linear/spot/etc.)."""
    try:
        with _client(base_url) as client:
            r = client.get("/v5/market/tickers", params={"category": category})
            r.raise_for_status()
            return r.json().get("result", {}).get("list", []) or []
    except Exception:
        return []


def fetch_ticker(symbol: str, category: str = "linear", base_url: Optional[str] = None) -> dict:
    """Return a single Bybit ticker (dict) for a symbol."""
    try:
        params = {"category": category, "symbol": symbol.replace("/", "")}
        with _client(base_url) as client:
            r = client.get("/v5/market/tickers", params=params)
            r.raise_for_status()
            items = r.json().get("result", {}).get("list", []) or []
        return items[0] if items else {}
    except Exception:
        return {}


def fetch_instrument_info(symbol: str, category: str = "linear", base_url: Optional[str] = None) -> dict:
    """Return a single Bybit instrument info dict for a symbol."""
    try:
        params = {"category": category, "symbol": symbol.replace("/", "")}
        with _client(base_url) as client:
            r = client.get("/v5/market/instruments-info", params=params)
            r.raise_for_status()
            items = r.json().get("result", {}).get("list", []) or []
        return items[0] if items else {}
    except Exception:
        return {}
