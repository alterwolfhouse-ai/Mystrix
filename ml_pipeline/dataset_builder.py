"""Build divergence datasets with labels for the ML pipeline."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from engine.divergence import bear_divergence, bull_divergence, pivot_high, pivot_low  # noqa: E402

if "ml_pipeline" not in sys.modules:
    from ml_pipeline.data_loader import fetch_ohlcv  # type: ignore # noqa: E402
    from ml_pipeline.feature_engineering import add_indicators, base_features  # type: ignore # noqa: E402
else:
    from .data_loader import fetch_ohlcv  # noqa: E402
    from .feature_engineering import add_indicators, base_features  # noqa: E402


def add_htf_context(df: pd.DataFrame, htf_minutes: int = 30) -> pd.DataFrame:
    df = df.copy()
    htf_freq = f"{htf_minutes}T"
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    resampled = df[["open", "high", "low", "close", "volume"]].resample(htf_freq).agg(agg)
    resampled = add_indicators(resampled)
    resampled = resampled.rename(columns={"rsi": "htf_rsi", "ema21": "htf_ema21", "ema55": "htf_ema55"})
    htf = resampled[["htf_rsi", "htf_ema21", "htf_ema55"]].reindex(df.index, method="ffill")
    df[["htf_rsi", "htf_ema21", "htf_ema55"]] = htf
    df["htf_trend_slope"] = df["htf_ema21"] - df["htf_ema55"]
    df["htf_trend_dir"] = np.sign(df["htf_trend_slope"])
    df["htf_trend_strength"] = np.abs(df["htf_trend_slope"]) / (df["atr"] + 1e-6)
    bins = [-np.inf, 30, 50, 70, np.inf]
    labels = [0, 1, 2, 3]
    df["htf_rsi_regime"] = pd.cut(df["htf_rsi"], bins=bins, labels=labels).astype(float)
    return df


def add_sr_context(df: pd.DataFrame, lookback: int = 480) -> pd.DataFrame:
    df = df.copy()
    rolling_high = df["high"].rolling(lookback, min_periods=1).max()
    rolling_low = df["low"].rolling(lookback, min_periods=1).min()
    dist_high = np.abs(rolling_high - df["close"])
    dist_low = np.abs(df["close"] - rolling_low)
    dist_sr = np.minimum(dist_high, dist_low)
    df["sr_proximity"] = np.exp(-(dist_sr / (df["atr"] + 1e-6)))
    df["range_context"] = (rolling_high - rolling_low) / (df["atr"] + 1e-6)
    return df


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    direction: int
    entry_idx: int
    exit_idx: int
    label: int
    hit_target: int
    hit_stop: int
    ret_pct: float
    features: dict


def divergence_strength_features(df: pd.DataFrame, prev_idx: int | None, curr_idx: int | None, direction: int) -> dict:
    if prev_idx is None or curr_idx is None or prev_idx < 0:
        return {
            "div_price_change_pct": 0.0,
            "div_rsi_change": 0.0,
            "div_ratio": 0.0,
            "div_price_slope": 0.0,
            "div_rsi_slope": 0.0,
            "div_slope_disagreement": 0.0,
            "div_price_range_atr": 0.0,
            "div_rsi_distance": 0.0,
            "div_trend_slope": 0.0,
            "div_trend_strength": 0.0,
            "div_vol_regime": 0.0,
        }
    price1 = df["close"].iloc[prev_idx]
    price2 = df["close"].iloc[curr_idx]
    rsi1 = df["rsi"].iloc[prev_idx]
    rsi2 = df["rsi"].iloc[curr_idx]
    bars_between = max(curr_idx - prev_idx, 1)
    atr = float(df["atr"].iloc[curr_idx])
    ema_context = float(df["ema55"].iloc[curr_idx]) or 1e-6

    price_change_pct = (price2 - price1) / price1 * 100
    rsi_change = rsi2 - rsi1
    div_ratio = abs(rsi_change) / (abs(price_change_pct) + 1e-6)
    price_slope = (price2 - price1) / bars_between
    rsi_slope = (rsi2 - rsi1) / bars_between
    slope_disagreement = price_slope * rsi_slope
    price_range_atr = abs(price2 - price1) / (atr + 1e-6)
    regime_anchor = 30 if direction == 1 else 70
    rsi_distance = ((rsi1 + rsi2) / 2) - regime_anchor
    trend_slope = float(df["ema21"].iloc[curr_idx] - df["ema55"].iloc[curr_idx])
    trend_strength = abs(trend_slope) / (atr + 1e-6)
    vol_regime = atr / abs(ema_context)

    return {
        "div_price_change_pct": price_change_pct,
        "div_rsi_change": rsi_change,
        "div_ratio": div_ratio,
        "div_price_slope": price_slope,
        "div_rsi_slope": rsi_slope,
        "div_slope_disagreement": slope_disagreement,
        "div_price_range_atr": price_range_atr,
        "div_rsi_distance": rsi_distance,
        "div_trend_slope": trend_slope,
        "div_trend_strength": trend_strength,
        "div_vol_regime": vol_regime,
    }


def build_trades(
    df: pd.DataFrame,
    symbol: str,
    stop_pct: float = 0.03,
    target_pct: float = 0.015,
    lb_left: int = 5,
    lb_right: int = 5,
    range_low: int = 5,
    range_up: int = 60,
) -> List[Trade]:
    bull = bull_divergence(df["rsi"], df["low"], lb_left, lb_right, range_low, range_up).fillna(False)
    bear = bear_divergence(df["rsi"], df["high"], lb_left, lb_right, range_low, range_up).fillna(False)
    pl_mask = pivot_low(df["rsi"], lb_left, lb_right)
    ph_mask = pivot_high(df["rsi"], lb_left, lb_right)
    trades: List[Trade] = []
    long_entry = None
    short_entry = None
    long_feat = {}
    short_feat = {}
    prev_low_idx = None
    last_low_idx = None
    prev_high_idx = None
    last_high_idx = None
    cluster_window = 200
    cluster_cap = 3
    recent_bulls: deque[int] = deque()
    recent_bears: deque[int] = deque()

    for idx, ts in enumerate(df.index):
        while recent_bulls and idx - recent_bulls[0] > cluster_window:
            recent_bulls.popleft()
        while recent_bears and idx - recent_bears[0] > cluster_window:
            recent_bears.popleft()

        if pl_mask.iloc[idx]:
            prev_low_idx = last_low_idx
            last_low_idx = idx
        if ph_mask.iloc[idx]:
            prev_high_idx = last_high_idx
            last_high_idx = idx

        if bear.loc[ts]:
            if long_entry is not None:
                trades.append(close_trade(df, long_entry, ts, +1, long_feat, stop_pct, target_pct))
                long_entry = None
            if short_entry is None:
                short_entry = ts
                short_feat = base_features(df, ts, -1, symbol)
                short_feat.update(divergence_strength_features(df, prev_high_idx, last_high_idx, -1))
                cluster_strength = min(len(recent_bears), cluster_cap) / cluster_cap
                short_feat["cluster_strength"] = cluster_strength
                recent_bears.append(idx)
        if bull.loc[ts]:
            if short_entry is not None:
                trades.append(close_trade(df, short_entry, ts, -1, short_feat, stop_pct, target_pct))
                short_entry = None
            if long_entry is None:
                long_entry = ts
                long_feat = base_features(df, ts, +1, symbol)
                long_feat.update(divergence_strength_features(df, prev_low_idx, last_low_idx, +1))
                cluster_strength = min(len(recent_bulls), cluster_cap) / cluster_cap
                long_feat["cluster_strength"] = cluster_strength
                recent_bulls.append(idx)
    trades = [t for t in trades if t is not None]
    return trades


def close_trade(
    df: pd.DataFrame,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    direction: int,
    feat: dict,
    stop_pct: float,
    target_pct: float,
) -> Trade | None:
    entry_idx = df.index.get_loc(entry_ts)
    exit_idx = df.index.get_loc(exit_ts)
    if exit_idx <= entry_idx:
        return None
    entry_price = df.at[entry_ts, "close"]
    exit_price = df.at[exit_ts, "close"]
    window = df.iloc[entry_idx : exit_idx + 1]
    if direction == 1:
        stop_price = entry_price * (1 - stop_pct)
        target_price = entry_price * (1 + target_pct)
        hit_target, hit_stop = evaluate_path_long(window, target_price, stop_price)
        final_ret = (exit_price / entry_price - 1) * 100
    else:
        stop_price = entry_price * (1 + stop_pct)
        target_price = entry_price * (1 - target_pct)
        hit_target, hit_stop = evaluate_path_short(window, target_price, stop_price)
        final_ret = ((entry_price / exit_price) - 1) * 100
    label = int(hit_target and not hit_stop)
    return Trade(
        entry_time=entry_ts,
        exit_time=exit_ts,
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        direction=direction,
        entry_idx=entry_idx,
        exit_idx=exit_idx,
        label=label,
        hit_target=int(hit_target),
        hit_stop=int(hit_stop),
        ret_pct=final_ret,
        features=feat,
    )


def evaluate_path_long(window: pd.DataFrame, target_price: float, stop_price: float) -> tuple[bool, bool]:
    hit_target = False
    hit_stop = False
    for _, row in window.iterrows():
        if row["high"] >= target_price:
            hit_target = True
            break
        if row["low"] <= stop_price:
            hit_stop = True
            break
    if not hit_target and not hit_stop:
        # price never hit target or stop before exit; treat as neutral (label 0)
        hit_stop = False
    return hit_target, hit_stop


def evaluate_path_short(window: pd.DataFrame, target_price: float, stop_price: float) -> tuple[bool, bool]:
    hit_target = False
    hit_stop = False
    for _, row in window.iterrows():
        if row["low"] <= target_price:
            hit_target = True
            break
        if row["high"] >= stop_price:
            hit_stop = True
            break
    if not hit_target and not hit_stop:
        hit_stop = False
    return hit_target, hit_stop


def trades_to_frame(trades: List[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    rows = []
    for t in trades:
        duration_min = (t.exit_time - t.entry_time).total_seconds() / 60.0
        row = {
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "direction": t.direction,
            "entry_idx": t.entry_idx,
            "exit_idx": t.exit_idx,
            "label": t.label,
             "hit_target": t.hit_target,
             "hit_stop": t.hit_stop,
            "ret_pct": t.ret_pct,
            "holding_minutes": duration_min,
        }
        row.update(t.features)
        rows.append(row)
    return pd.DataFrame(rows).dropna()


def build_dataset(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str | None = None,
    stop_pct: float = 0.03,
    target_pct: float = 0.015,
    log: list[str] | None = None,
    cache_root: Path | None = None,
) -> pd.DataFrame:
    raw = fetch_ohlcv(symbol, timeframe, start_date, end_date, log=log, cache_root=cache_root)
    enriched = add_indicators(raw)
    enriched = add_htf_context(enriched)
    enriched = add_sr_context(enriched)
    trades = build_trades(enriched, symbol, stop_pct=stop_pct, target_pct=target_pct)
    df = trades_to_frame(trades)
    print(f"[dataset] {symbol} rows: {len(df)}")
    return df
