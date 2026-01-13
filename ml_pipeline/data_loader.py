"""Data loading utilities for the MystriX ML pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from engine.storage import get_ohlcv  # noqa: E402
from engine.data import fetch_ccxt_hist_range  # noqa: E402

TF_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
}


def _infer_dates(
    start: Optional[str], end: Optional[str], timeframe: str, limit: Optional[int] = None
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = pd.to_datetime(end) if end else pd.Timestamp.utcnow()
    end_ts = end_ts.tz_localize(None)
    if start:
        start_ts = pd.to_datetime(start)
    else:
        bars = limit or 5000
        minutes = TF_MINUTES.get(timeframe, 3)
        start_ts = end_ts - pd.Timedelta(minutes=minutes * (bars + 50))
    start_ts = start_ts.tz_localize(None)
    return start_ts, end_ts


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    start: Optional[str],
    end: Optional[str],
    chunk_days: int = 90,
    log: Optional[list[str]] = None,
    cache_root: Optional[Path] = None,
) -> pd.DataFrame:
    """Fetch OHLCV in manageable chunks (default 90d) with basic failover."""
    start_ts, end_ts = _infer_dates(start, end, timeframe)
    frames: list[pd.DataFrame] = []
    segments = []
    cur_end = end_ts
    while cur_end > start_ts:
        cur_start = max(start_ts, cur_end - pd.Timedelta(days=chunk_days))
        segments.append((cur_start, cur_end))
        cur_end = cur_start
    segments = list(reversed(segments))  # forward in time

    for (seg_start, seg_end) in segments:
        if log is not None:
            log.append(f"{symbol}: chunk {seg_start.date()} -> {seg_end.date()}")
        try:
            df_chunk = get_ohlcv(symbol, timeframe, seg_start.isoformat(), seg_end.isoformat(), cache_root=cache_root)
            if df_chunk.empty:
                raise ValueError("empty chunk")
        except Exception:
            df_chunk = fetch_ccxt_hist_range(symbol, timeframe, seg_start.isoformat(), seg_end.isoformat())
        frames.append(df_chunk)

    if not frames:
        return pd.DataFrame(columns=["open","high","low","close","volume"], index=pd.to_datetime([]))
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    print(f"[data] {symbol} aggregated bars: {len(df)}")
    return df
