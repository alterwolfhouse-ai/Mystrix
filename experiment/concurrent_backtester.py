from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import heapq
import itertools
import numpy as np
import pandas as pd

from ml_pipeline.ml_filter import MLFilter


def _parse_optional_date(value: Optional[str]) -> Optional[pd.Timestamp]:
    if not value:
        return None
    try:
        return pd.Timestamp(value)
    except Exception:
        try:
            return pd.Timestamp(value.split("T")[0])
        except Exception:
            return None


def _norm_symbol(sym: str) -> str:
    s = sym.strip().upper()
    if "/" in s:
        return s
    if s.endswith("USDT"):
        return s[:-4] + "/USDT"
    return f"{s}/USDT"


@dataclass
class ConcurrentBacktestConfig:
    dataset_path: Path
    model_path: Optional[Path] = None
    threshold: float = 0.65
    symbols: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_equity: float = 10_000.0
    equity_pct: float = 0.5
    fee_bps: float = 5.0
    max_positions: int = 20
    max_assets: int = 20


def _load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    df = pd.read_csv(path)
    if "entry_time" not in df.columns or "exit_time" not in df.columns:
        raise ValueError("dataset must contain entry_time/exit_time columns")
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    return df


def _ensure_symbols(df: pd.DataFrame, cfg: ConcurrentBacktestConfig) -> pd.DataFrame:
    df["symbol"] = df["symbol"].astype(str).str.upper()
    allowed: List[str]
    if cfg.symbols:
        allowed = [_norm_symbol(sym) for sym in cfg.symbols]
    else:
        freq = df["symbol"].value_counts().sort_values(ascending=False)
        allowed = list(freq.head(cfg.max_assets).index)
    return df[df["symbol"].isin(allowed)].copy()


def _prepare_filter(df: pd.DataFrame, cfg: ConcurrentBacktestConfig) -> Tuple[pd.DataFrame, bool]:
    if cfg.model_path and cfg.model_path.exists():
        ml = MLFilter(cfg.model_path)
        missing = [col for col in ml.all_cols if col not in df.columns]
        for col in missing:
            if col == "symbol":
                df[col] = df["symbol"]
            else:
                df[col] = 0.0
        probs = ml.batch_probabilities(df)
        df["ml_prob"] = probs
        df["ml_action"] = df["ml_prob"] >= cfg.threshold
        return df[df["ml_action"]].copy(), True
    else:
        df["ml_prob"] = 1.0
        df["ml_action"] = True
        return df.copy(), False


def _calc_ret(row: pd.Series) -> float:
    ret = row.get("ret_pct")
    if pd.isna(ret) or ret == 0:
        entry = float(row.get("entry_price", 0.0) or 0.0)
        exit_price = float(row.get("exit_price", entry))
        direction = 1 if float(row.get("direction", 1)) >= 0 else -1
        if entry == 0:
            return 0.0
        ret = ((exit_price - entry) / entry) * 100.0 * direction
    return float(ret)


def _calc_cagr(initial: float, final: float, start: pd.Timestamp, end: pd.Timestamp) -> float:
    if initial <= 0 or final <= 0 or start >= end:
        return 0.0
    years = (end - start).days / 365.0
    if years <= 0:
        return 0.0
    return (final / initial) ** (1 / years) - 1


def run_concurrent_backtest(cfg: ConcurrentBacktestConfig) -> Dict[str, Any]:
    df = _load_dataset(cfg.dataset_path)
    df = _ensure_symbols(df, cfg)
    if df.empty:
        raise ValueError("No trades found for the selected symbols/dataset")

    start_ts = _parse_optional_date(cfg.start_date)
    end_ts = _parse_optional_date(cfg.end_date)
    if start_ts is not None:
        df = df[df["entry_time"] >= start_ts]
    if end_ts is not None:
        df = df[df["entry_time"] <= end_ts]
    if df.empty:
        raise ValueError("No trades remain after applying the date filters")

    taken_df, filter_used = _prepare_filter(df, cfg)
    signal_count = int(len(df))
    taken_count = int(len(taken_df))

    if taken_count == 0:
        return {
            "summary": {
                "message": "Model rejected all signals for the given configuration",
                "signals": signal_count,
                "filtered": 0,
                "model_ready": filter_used,
            },
            "equity_curve": [],
            "trades": [],
            "symbols": [],
            "concurrency": [],
        }

    taken_df = taken_df.sort_values("entry_time").reset_index(drop=True)
    taken_df["ret_clean"] = taken_df.apply(_calc_ret, axis=1)

    equity = cfg.initial_equity
    peak_equity = equity
    max_drawdown = 0.0
    max_concurrent = 0
    wins = 0
    losses = 0
    capacity_skipped = 0

    equity_curve: List[Dict[str, Any]] = [{"t": taken_df.iloc[0]["entry_time"].isoformat(), "equity": equity}]
    trade_records: List[Dict[str, Any]] = []
    symbol_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0, "minutes": 0.0})
    concurrency_track: List[Dict[str, Any]] = []

    heap: List[Tuple[pd.Timestamp, int, Dict[str, Any]]] = []
    counter = itertools.count()

    def settle_until(current_time: pd.Timestamp):
        nonlocal equity, peak_equity, max_drawdown, wins, losses
        while heap and heap[0][0] <= current_time:
            exit_time, _, pos = heapq.heappop(heap)
            equity_before = equity
            pnl = pos["size"] * (pos["ret_pct"] / 100.0)
            fee = pos["size"] * (cfg.fee_bps / 10000.0) * 2.0
            net = pnl - fee
            equity += net
            symbol_stats[pos["symbol"]]["trades"] += 1
            symbol_stats[pos["symbol"]]["pnl"] += net
            symbol_stats[pos["symbol"]]["minutes"] += pos["duration"]
            if net >= 0:
                wins += 1
                symbol_stats[pos["symbol"]]["wins"] += 1
            else:
                losses += 1
            equity_curve.append({"t": exit_time.isoformat(), "equity": equity})
            if equity > peak_equity:
                peak_equity = equity
            drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0
            if drawdown < max_drawdown:
                max_drawdown = drawdown
            trade_records.append(
                {
                    "symbol": pos["symbol"],
                    "entry_time": pos["entry_time"].isoformat(),
                    "exit_time": exit_time.isoformat(),
                    "entry_price": pos.get("entry_price"),
                    "exit_price": pos.get("exit_price"),
                    "size": pos["size"],
                    "ret_pct": pos["ret_pct"],
                    "gross_pnl": pnl,
                    "fee_paid": fee,
                    "net_pnl": net,
                    "prob": pos["prob"],
                    "direction": pos["direction"],
                    "equity_before": equity_before,
                    "equity_after": equity,
                    "hold_minutes": pos["duration"],
                    "side": "bull" if pos["direction"] >= 0 else "bear",
                    "status": "taken",
                }
            )

    for _, row in taken_df.iterrows():
        entry_time = row["entry_time"]
        settle_until(entry_time)
        if cfg.max_positions and len(heap) >= cfg.max_positions:
            capacity_skipped += 1
            continue
        position_size = equity * cfg.equity_pct
        duration = (row["exit_time"] - row["entry_time"]).total_seconds() / 60.0
        entry_price = float(row.get("entry_price", 0.0) or 0.0)
        exit_price = float(row.get("exit_price", entry_price) or entry_price)
        pos = {
            "symbol": row["symbol"],
            "size": position_size,
            "ret_pct": row["ret_clean"],
            "entry_time": entry_time,
            "exit_time": row["exit_time"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "prob": float(row.get("ml_prob", 1.0)),
            "direction": int(row.get("direction", 1)),
            "duration": duration,
        }
        heapq.heappush(heap, (row["exit_time"], next(counter), pos))
        concurrency_track.append({"t": entry_time.isoformat(), "concurrency": len(heap)})
        max_concurrent = max(max_concurrent, len(heap))

    while heap:
        settle_until(heap[0][0])

    final_equity = equity
    total_pnl = final_equity - cfg.initial_equity
    if equity_curve:
        start_curve = pd.Timestamp(equity_curve[0]["t"])
        end_curve = pd.Timestamp(equity_curve[-1]["t"])
    else:
        start_curve = taken_df.iloc[0]["entry_time"]
        end_curve = taken_df.iloc[-1]["exit_time"]
    cagr = _calc_cagr(cfg.initial_equity, final_equity, start_curve, end_curve)
    stats = []
    for sym, data in symbol_stats.items():
        trades = data["trades"]
        if trades == 0:
            continue
        avg_minutes = data["minutes"] / trades if trades else 0.0
        stats.append(
            {
                "symbol": sym,
                "trades": trades,
                "win_rate": (data["wins"] / trades) * 100 if trades else 0.0,
                "pnl": data["pnl"],
                "avg_minutes": avg_minutes,
                "return_pct": (data["pnl"] / cfg.initial_equity) * 100,
            }
        )
    stats.sort(key=lambda x: x["pnl"], reverse=True)

    trades_sorted = sorted(trade_records, key=lambda x: x["exit_time"], reverse=True)

    summary = {
        "initial_equity": cfg.initial_equity,
        "final_equity": final_equity,
        "total_return_pct": (final_equity / cfg.initial_equity - 1) * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": abs(max_drawdown) * 100,
        "trades": wins + losses,
        "win_rate_pct": (wins / (wins + losses) * 100) if (wins + losses) else 0.0,
        "signals": signal_count,
        "filtered": taken_count,
        "skipped_capacity": capacity_skipped,
        "max_concurrent": max_concurrent,
        "model_ready": filter_used,
    }

    return {
        "summary": summary,
        "equity_curve": equity_curve,
        "trades": trades_sorted[:750],  # limit payload, newest first
        "symbols": stats,
        "concurrency": concurrency_track,
    }
