#!/usr/bin/env python3
"""MystriX+ experiment runner.

This module removes the RSI arming gate and routes every divergence through the
trained ML filter. The filter decides whether a divergence should be executed,
and we log the resulting trades in a simple equity curve backtest.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from ml_pipeline.dataset_builder import build_dataset  # noqa: E402
from ml_pipeline.ml_filter import MLFilter  # noqa: E402


@dataclass
class PlusExperimentConfig:
    """Parameters driving the divergence → ML → execution experiment."""

    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "3m"
    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    stop_pct: float = 0.03
    target_pct: float = 0.015
    dataset_path: Optional[str] = "ml_pipeline/data/div_all_3m.csv"
    model_path: str = "ml_pipeline/models/ml_filter.pkl"
    ml_threshold: float = 0.65
    initial_capital: float = 10_000.0
    equity_risk: float = 0.02
    holding_minutes_hint: float = 0.0
    log_skipped: bool = False

    def start_ts(self) -> pd.Timestamp:
        return pd.Timestamp(self.start_date)

    def end_ts(self) -> Optional[pd.Timestamp]:
        return pd.Timestamp(self.end_date) if self.end_date else None


def _load_combined_dataset(path: Optional[str]) -> Optional[pd.DataFrame]:
    if not path:
        return None
    data_path = Path(path)
    if not data_path.exists():
        return None
    df = pd.read_csv(data_path, parse_dates=["entry_time", "exit_time"])
    return df


def _slice_dataset(
    combined: Optional[pd.DataFrame], symbol: str, cfg: PlusExperimentConfig
) -> pd.DataFrame:
    if combined is not None:
        df = combined[combined["symbol"] == symbol].copy()
        if df.empty:
            return df
        df = df[df["entry_time"] >= cfg.start_ts()]
        if cfg.end_ts() is not None:
            df = df[df["entry_time"] <= cfg.end_ts()]
        return df.reset_index(drop=True)
    # Fall back to on-demand dataset build (slower but fresh)
    return build_dataset(
        symbol,
        cfg.timeframe,
        cfg.start_date,
        cfg.end_date,
        stop_pct=cfg.stop_pct,
        target_pct=cfg.target_pct,
    )


def _max_drawdown(equity_curve: Iterable[float], start_equity: float) -> float:
    equity = np.array([start_equity, *equity_curve], dtype=float)
    if equity.size <= 1:
        return 0.0
    cummax = np.maximum.accumulate(equity)
    dd = equity / cummax - 1.0
    return float(dd.min() * 100.0)


def _run_symbol(
    symbol: str,
    dataset: pd.DataFrame,
    ml_filter: MLFilter,
    cfg: PlusExperimentConfig,
    equity_state: Dict[str, float],
) -> Tuple[List[dict], float]:
    logs: List[dict] = []
    if dataset.empty:
        return logs, equity_state["equity"]

    dataset = dataset.sort_values("entry_time").reset_index(drop=True)
    equity = equity_state["equity"]
    for _, trade in dataset.iterrows():
        feat = {col: trade[col] for col in ml_filter.all_cols if col in trade}
        if "holding_minutes" not in feat or pd.isna(feat["holding_minutes"]):
            feat["holding_minutes"] = cfg.holding_minutes_hint
        result = ml_filter.score(feat, threshold=cfg.ml_threshold)
        direction_flag = int(trade.get("direction", 0))
        divergence = "bull" if direction_flag > 0 else "bear"
        event = {
            "symbol": symbol,
            "direction": int(trade.get("direction", 0)),
            "divergence": divergence,
            "entry_time": trade["entry_time"],
            "exit_time": trade["exit_time"],
            "entry_price": float(trade.get("entry_price", np.nan)),
            "exit_price": float(trade.get("exit_price", np.nan)),
            "ret_pct": float(trade.get("ret_pct", 0.0)),
            "ml_action": result.action,
            "ml_confidence": result.confidence,
            "ml_risk_multiplier": result.risk_multiplier,
            "label": int(trade.get("label", -1)),
        }
        take_trade = result.action == "take"
        if take_trade:
            risk_amt = equity * cfg.equity_risk
            event["trade_size"] = risk_amt
            pnl = risk_amt * (event["ret_pct"] / 100.0)
            equity += pnl
            event["status"] = "taken"
            event["pnl"] = pnl
            event["equity_after"] = equity
        else:
            event["status"] = "skipped"
            event["pnl"] = 0.0
            event["equity_after"] = equity
        if take_trade or cfg.log_skipped:
            logs.append(event)
    equity_state["equity"] = equity
    return logs, equity


def run_experiment(cfg: PlusExperimentConfig) -> Tuple[pd.DataFrame, Dict[str, float]]:
    ml_filter = MLFilter(Path(cfg.model_path))
    combined = _load_combined_dataset(cfg.dataset_path)
    equity_state = {"equity": cfg.initial_capital}
    logs: List[dict] = []

    for symbol in cfg.symbols:
        dataset = _slice_dataset(combined, symbol, cfg)
        symbol_logs, _ = _run_symbol(symbol, dataset, ml_filter, cfg, equity_state)
        logs.extend(symbol_logs)

    trades_df = pd.DataFrame(logs)
    if not trades_df.empty:
        trades_df = trades_df.sort_values("entry_time").reset_index(drop=True)
        trades_df.insert(0, "trade_no", range(1, len(trades_df) + 1))
    summary = _summarize(trades_df, cfg)
    series = _build_series(trades_df, cfg)
    return trades_df, summary, series


def _summarize(trades: pd.DataFrame, cfg: PlusExperimentConfig) -> Dict[str, float]:
    summary = {
        "initial_capital": cfg.initial_capital,
        "final_equity": cfg.initial_capital,
        "total_return_pct": 0.0,
        "num_trades": 0,
        "win_rate_pct": 0.0,
        "avg_pnl": 0.0,
        "max_drawdown_pct": 0.0,
        "skipped_divergences": 0,
    }
    if trades.empty:
        return summary

    taken = trades[trades["status"] == "taken"].copy()
    summary["skipped_divergences"] = int((trades["status"] == "skipped").sum())
    if taken.empty:
        return summary

    final_equity = float(taken["equity_after"].iloc[-1])
    pnl_series = taken["pnl"]
    wins = int((pnl_series > 0).sum())
    bull_count = int((taken.get("divergence") == "bull").sum()) if "divergence" in taken.columns else 0
    bear_count = int((taken.get("divergence") == "bear").sum()) if "divergence" in taken.columns else 0

    summary.update(
        {
            "final_equity": final_equity,
            "total_return_pct": (final_equity / cfg.initial_capital - 1.0) * 100.0,
            "num_trades": int(len(taken)),
            "win_rate_pct": (wins / len(taken)) * 100.0 if len(taken) else 0.0,
            "avg_pnl": float(pnl_series.mean()) if not pnl_series.empty else 0.0,
            "max_drawdown_pct": _max_drawdown(taken["equity_after"], cfg.initial_capital),
            "divergence_counts": {"bull": bull_count, "bear": bear_count},
        }
    )
    return summary


def _build_series(trades: pd.DataFrame, cfg: PlusExperimentConfig) -> Dict[str, List[Dict[str, float]]]:
    if trades.empty:
        return {"combined": [], "bull": [], "bear": []}

    taken = trades[trades["status"] == "taken"].copy()
    if taken.empty:
        return {"combined": [], "bull": [], "bear": []}

    taken = taken.sort_values("exit_time")

    def build(df: pd.DataFrame) -> List[Dict[str, float]]:
        eq = cfg.initial_capital
        points: List[Dict[str, float]] = []
        for _, row in df.iterrows():
            eq += float(row.get("pnl", 0.0))
            ts = row.get("exit_time")
            if isinstance(ts, pd.Timestamp):
                ts = ts.isoformat()
            else:
                ts = str(ts)
            points.append({"t": ts, "equity": eq})
        return points

    return {
        "combined": build(taken),
        "bull": build(taken[taken["divergence"] == "bull"]),
        "bear": build(taken[taken["divergence"] == "bear"]),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MystriX+ divergence ML experiment.")
    parser.add_argument("--symbols", default="BTC/USDT", help="Comma-separated list of symbols.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--timeframe", default="3m")
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--equity-risk", type=float, default=0.02)
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--model", default="ml_pipeline/models/ml_filter.pkl")
    parser.add_argument("--dataset", default="ml_pipeline/data/div_all_3m.csv")
    parser.add_argument("--log-out", default="experiment/logs/mystrix_plus_trades.csv")
    parser.add_argument("--stop-pct", type=float, default=0.03)
    parser.add_argument("--target-pct", type=float, default=0.015)
    parser.add_argument("--holding-minutes-hint", type=float, default=0.0)
    parser.add_argument("--log-skipped", action="store_true", help="Persist skipped divergences as well.")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    cfg = PlusExperimentConfig(
        symbols=symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        ml_threshold=float(args.threshold),
        equity_risk=float(args.equity_risk),
        initial_capital=float(args.initial_capital),
        model_path=args.model,
        dataset_path=args.dataset,
        timeframe=args.timeframe,
        stop_pct=float(args.stop_pct),
        target_pct=float(args.target_pct),
        holding_minutes_hint=float(args.holding_minutes_hint),
        log_skipped=bool(args.log_skipped),
    )
    trades_df, summary, _ = run_experiment(cfg)
    out_path = Path(args.log_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(out_path, index=False)

    print("=== MystriX+ Experiment Summary ===")
    for key, val in summary.items():
        print(f"{key}: {val}")
    print(f"\nDetailed trade log written to: {out_path}")


if __name__ == "__main__":
    main()

