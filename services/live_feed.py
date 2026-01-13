from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from engine.bybit_data import fetch_klines, BYBIT_MAINNET
from engine.divergence import bear_divergence, bull_divergence, pivot_high, pivot_low
from ml_pipeline.feature_engineering import add_indicators, base_features
from ml_pipeline.dataset_builder import (
    add_htf_context,
    add_sr_context,
    divergence_strength_features,
)
from ml_pipeline.ml_filter import MLFilter
from utils.symbols import norm_symbol

LOG_PATH = Path("live_feed.log")
_LAST_EMITTED: Dict[Tuple[str, str], str] = {}
# Freshness guards (very lenient to surface signals; still block stale price)
MAX_DIVERGENCE_AGE_BARS = 500        # effectively allow many bars back
MAX_DIVERGENCE_AGE_MINUTES = 1440    # up to 24h divergence age
MAX_PRICE_STALENESS_MINUTES = 10     # require last price candle to be recent


def _log_json(payload: Dict[str, Any]) -> None:
    """Append a JSON log line for debugging feeder vs ML outputs."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except Exception:
        # logging must never block feed
        pass


@lru_cache(maxsize=4)
def _load_filter(model_path: str) -> MLFilter:
    return MLFilter(Path(model_path))


def _latest_divergence_indices(df: pd.DataFrame, direction: int) -> Optional[Tuple[pd.Timestamp, int, int]]:
    """Return the latest divergence timestamp and pivot indices for strength features."""
    lb_left, lb_right, range_low, range_up = 5, 5, 5, 60
    if direction == 1:
        mask = bull_divergence(df["rsi"], df["low"], lb_left, lb_right, range_low, range_up)
        pivots = pivot_low(df["rsi"], lb_left, lb_right)
    else:
        mask = bear_divergence(df["rsi"], df["high"], lb_left, lb_right, range_low, range_up)
        pivots = pivot_high(df["rsi"], lb_left, lb_right)
    if not mask.any():
        return None
    ts = mask[mask].index[-1]
    pivot_positions = [i for i, flag in enumerate(pivots) if flag]
    prev_idx = pivot_positions[-2] if len(pivot_positions) >= 2 else (pivot_positions[-1] if pivot_positions else None)
    last_idx = pivot_positions[-1] if pivot_positions else None
    return ts, prev_idx, last_idx


def _cluster_strength(div_mask: pd.Series, window: int = 200, cap: int = 3) -> float:
    if div_mask.empty:
        return 0.0
    recent = div_mask.tail(window)
    count = int(recent.sum())
    return min(count, cap) / float(cap)


def _build_features(df: pd.DataFrame, ts: pd.Timestamp, direction: int, prev_idx: int | None, last_idx: int | None, symbol: str) -> Dict[str, Any]:
    feats = base_features(df, ts, direction, symbol)
    feats["holding_minutes"] = 0.0  # live signal has no realized hold yet
    feats.update(divergence_strength_features(df, prev_idx, last_idx, direction))
    # cluster strength uses divergence flags of the same direction
    if direction == 1:
        div_mask = bull_divergence(df["rsi"], df["low"], 5, 5, 5, 60)
    else:
        div_mask = bear_divergence(df["rsi"], df["high"], 5, 5, 5, 60)
    feats["cluster_strength"] = _cluster_strength(div_mask)
    return feats


def _prepare_df(sym: str, timeframe: str, bars: int = 400) -> pd.DataFrame:
    df = fetch_klines(sym, timeframe=timeframe, limit=bars, category="linear", base_url=BYBIT_MAINNET)
    if df.empty:
        return df
    if "volume" not in df.columns:
        if "volume_base" in df.columns:
            df = df.rename(columns={"volume_base": "volume"})
        else:
            df["volume"] = 0.0
    df = add_indicators(df)
    df = add_htf_context(df)
    df = add_sr_context(df)
    # forward-fill any indicator gaps then drop rows without RSI (early bars)
    df = df.ffill().dropna(subset=["rsi", "ema21", "ema55", "atr"])
    return df


def detect_live_divergences(
    symbols: Iterable[str],
    model_path: str = "ml_pipeline/models/ml_filter.pkl",
    threshold: float = 0.65,
    timeframe: str = "3m",
    max_events: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch fresh OHLCV, detect latest divergence per symbol, score with ML, and emit events.

    Scans all symbols; optional max_events only trims the returned list after scanning.
    """
    events: List[Dict[str, Any]] = []
    model_error = None
    try:
        filt = _load_filter(model_path)
    except Exception as exc:
        filt = None
        model_error = str(exc)
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    for raw_sym in symbols:
        sym = norm_symbol(raw_sym)
        try:
            df = _prepare_df(sym, timeframe)
            if df.empty:
                _log_json({"ts": now, "symbol": sym, "event": "empty_df", "timeframe": timeframe})
                continue
            last_ts = df.index[-1]
            # Normalize timestamps to naive UTC for safe subtraction
            last_ts_naive = last_ts.tz_localize(None) if getattr(last_ts, "tzinfo", None) else last_ts
            price_age_min = (datetime.utcnow() - last_ts_naive).total_seconds() / 60.0
            if price_age_min > MAX_PRICE_STALENESS_MINUTES:
                _log_json({"ts": now, "symbol": sym, "event": "stale_price", "price_ts": last_ts.isoformat(), "price_age_min": price_age_min})
                continue

            # choose the most recent divergence of either direction
            bull_info = _latest_divergence_indices(df, direction=1)
            bear_info = _latest_divergence_indices(df, direction=-1)
            pick: Optional[Tuple[pd.Timestamp, int, int, int]] = None  # ts, prev_idx, last_idx, dir
            if bull_info:
                pick = (bull_info[0], bull_info[1], bull_info[2], 1)
            if bear_info and (pick is None or bear_info[0] > pick[0]):
                pick = (bear_info[0], bear_info[1], bear_info[2], -1)
            if pick is None:
                continue
            ts, prev_idx, last_idx, direction = pick

            # Skip stale divergences
            ts_pos = df.index.get_loc(ts)
            if isinstance(ts_pos, slice):
                ts_pos = ts_pos.start  # fallback if duplicated index
            bars_since = (len(df) - 1) - int(ts_pos)
            ts_naive = ts.tz_localize(None) if getattr(ts, "tzinfo", None) else ts
            age_min = (last_ts_naive - ts_naive).total_seconds() / 60.0
            # Soft gate: log stale divergences but do not drop them unless price is stale
            if bars_since > MAX_DIVERGENCE_AGE_BARS or age_min > MAX_DIVERGENCE_AGE_MINUTES:
                _log_json(
                    {
                        "ts": now,
                        "symbol": sym,
                        "event": "stale_divergence_passed",
                        "div_ts": ts.isoformat(),
                        "bars_since": bars_since,
                        "age_min": age_min,
                        "price_ts": last_ts.isoformat(),
                    }
                )

            feats = _build_features(df, ts, direction, prev_idx, last_idx, sym)
            if filt is not None:
                decision = filt.score(feats, threshold=threshold)
            else:
                class _Dummy:
                    confidence = 0.0
                    action = "skip"
                decision = _Dummy()
            entry_price = float(df.at[ts, "close"])
            rsi_at_entry = float(df.at[ts, "rsi"])
            event = {
                "trade_no": int(time.time() * 1000) % 1_000_000,
                "symbol": sym,
                "divergence": "bull" if direction == 1 else "bear",
                "entry_time": ts.isoformat(),
                "exit_time": None,
                "entry_price": entry_price,
                "exit_price": entry_price,
                "trade_size": 0.0,
                "ret_pct": 0.0,
                "pnl": 0.0,
                "price_timestamp": last_ts.isoformat(),
                "price_age_minutes": price_age_min,
                "divergence_age_bars": bars_since,
                "divergence_age_minutes": age_min,
                "rsi_at_entry": rsi_at_entry,
                "ml_confidence": decision.confidence,
                "ml_action": decision.action,
                "ml_error": model_error,
                "status": "taken" if decision.action == "take" else "rejected",
                "feeder_status": "divergence_detected",
                "source": "live_v2",
            }
            # De-dupe by symbol/divergence/entry_time so we don't spam repeats
            key = (sym, event["divergence"])
            if _LAST_EMITTED.get(key) == event["entry_time"]:
                _log_json({"ts": now, "symbol": sym, "divergence": event["divergence"], "entry_time": event["entry_time"], "skipped": "duplicate"})
                continue
            _LAST_EMITTED[key] = event["entry_time"]
            events.append(event)
            _log_json(
                {
                    "ts": now,
                    "symbol": sym,
                    "divergence": event["divergence"],
                    "entry_time": event["entry_time"],
                    "price_ts": last_ts.isoformat(),
                    "price_age_min": price_age_min,
                    "divergence_age_bars": bars_since,
                    "divergence_age_min": age_min,
                    "price": entry_price,
                    "rsi": rsi_at_entry,
                    "decision": decision.action,
                    "confidence": decision.confidence,
                    "feeder": "ok",
                }
            )
        except Exception as exc:
            _log_json({"ts": now, "symbol": sym, "error": str(exc), "feeder": "error"})
            continue
    if max_events:
        return events[:max_events]
    return events
