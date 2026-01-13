#!/usr/bin/env python3
"""Grid-search over thresholds and risk for the ML filter."""

from __future__ import annotations

import argparse
from pathlib import Path
import itertools
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd

from ml_pipeline.ml_filter import MLFilter


def run_backtest(dataset: pd.DataFrame, probs: pd.Series, threshold: float, equity_risk: float, initial_capital: float):
    equity = initial_capital
    wins = losses = 0
    taken = 0
    for _, row in dataset.iterrows():
        prob = probs.loc[row.name]
        if prob < threshold:
            continue
        position_size = equity * equity_risk
        pnl = position_size * (row["ret_pct"] / 100.0)
        equity += pnl
        wins += int(pnl >= 0)
        losses += int(pnl < 0)
        taken += 1
    total_return = (equity / initial_capital - 1) * 100 if taken else 0.0
    win_rate = wins / taken * 100 if taken else 0.0
    return {"threshold": threshold, "equity_risk": equity_risk, "trades": taken, "win_rate": win_rate, "final_equity": equity, "total_return_pct": total_return}


def main():
    parser = argparse.ArgumentParser(description="Grid backtest the ML filter")
    parser.add_argument("--dataset-in", default="ml_pipeline/data/div_btc_2020.csv")
    parser.add_argument("--model", default="ml_pipeline/models/ml_filter.pkl")
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--thresholds", default="0.6,0.65,0.7,0.75,0.8,0.85,0.9")
    parser.add_argument("--risks", default="0.01,0.015,0.02,0.03")
    args = parser.parse_args()

    dataset = pd.read_csv(args.dataset_in)
    filt = MLFilter(Path(args.model))
    probs = pd.Series(filt.batch_probabilities(dataset), index=dataset.index)
    thresholds = [float(x) for x in args.thresholds.split(",")]
    risks = [float(x) for x in args.risks.split(",")]

    results = []
    for threshold, risk in itertools.product(thresholds, risks):
        summary = run_backtest(dataset, probs, threshold, risk, args.initial_capital)
        results.append(summary)

    df = pd.DataFrame(results)
    df = df.sort_values("total_return_pct", ascending=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
