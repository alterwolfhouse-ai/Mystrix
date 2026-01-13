#!/usr/bin/env python3
"""Simple backtest applying the ML filter to divergence trades."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd

from ml_pipeline.dataset_builder import build_dataset  # type: ignore
from ml_pipeline.ml_filter import MLFilter  # type: ignore


def run(args):
    if args.dataset_in and Path(args.dataset_in).exists():
        dataset = pd.read_csv(args.dataset_in)
    else:
        dataset = build_dataset(args.symbol, args.timeframe, args.start_date, args.end_date, stop_pct=args.stop_pct)
    dataset = dataset.sort_values("entry_time").reset_index(drop=True)
    filt = MLFilter(Path(args.model))
    equity = args.initial_capital
    equity_curve = []
    wins = losses = 0
    for _, row in dataset.iterrows():
        feat = {col: row[col] for col in filt.num_cols + filt.cat_cols}
        result = filt.score(feat, threshold=args.threshold)
        if result.action == "skip":
            continue
        size = equity * args.equity_risk
        pnl = size * (row["ret_pct"] / 100.0)
        equity += pnl
        wins += int(pnl >= 0)
        losses += int(pnl < 0)
        equity_curve.append(equity)
    if not equity_curve:
        print("[bt] no trades taken.")
        return
    final_return = (equity / args.initial_capital - 1) * 100
    print(f"[bt] trades taken: {wins + losses}, wins: {wins}, losses: {losses}")
    print(f"[bt] final equity: {equity:.2f} ({final_return:.2f}% return)")


def main():
    parser = argparse.ArgumentParser(description="Backtest the ML filter offline")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="3m")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--model", default="ml_pipeline/models/ml_filter.pkl")
    parser.add_argument("--dataset-in", default="ml_pipeline/data/div_btc_2020.csv")
    parser.add_argument("--stop-pct", type=float, default=0.03)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--equity-risk", type=float, default=0.25)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
