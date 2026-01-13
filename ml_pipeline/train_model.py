#!/usr/bin/env python3
"""Train and persist the ML divergence filter."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from ml_pipeline.dataset_builder import build_dataset  # type: ignore noqa


NUM_FEATURES = [
    "rsi",
    "price_vs_ema21",
    "price_vs_ema55",
    "mom3",
    "mom10",
    "vol_ratio",
    "atr_pct",
    "pullback20",
    "direction",
    "entry_hour",
    "entry_day",
    "holding_minutes",
    "div_price_change_pct",
    "div_rsi_change",
    "div_ratio",
    "div_price_slope",
    "div_rsi_slope",
    "div_slope_disagreement",
    "div_price_range_atr",
    "div_rsi_distance",
    "div_trend_slope",
    "div_trend_strength",
    "div_vol_regime",
    "htf_rsi",
    "htf_ema21",
    "htf_ema55",
    "htf_trend_slope",
    "htf_trend_strength",
    "htf_trend_dir",
    "htf_rsi_regime",
    "sr_proximity",
    "range_context",
    "cluster_strength",
]
CAT_FEATURES = ["symbol"]


def train_for_symbol(args):
    if args.dataset_in and Path(args.dataset_in).exists():
        dataset = pd.read_csv(args.dataset_in, parse_dates=["entry_time", "exit_time"])
        print(f"[dataset] loaded existing -> {args.dataset_in} rows={len(dataset)}")
    else:
        dataset = build_dataset(
            args.symbol,
            args.timeframe,
            args.start_date,
            args.end_date,
            stop_pct=args.stop_pct,
        )
        dataset = dataset.sort_values("entry_time").reset_index(drop=True)
        if args.dataset_out:
            out_path = Path(args.dataset_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            dataset.to_csv(out_path, index=False)
            print(f"[dataset] saved -> {out_path}")

    split_idx = int(len(dataset) * (1 - args.test_ratio))
    split_idx = max(1, min(split_idx, len(dataset) - 1))
    X = dataset[NUM_FEATURES + CAT_FEATURES]
    y = dataset["label"]
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), NUM_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ]
    )

    models = {
        "logreg": Pipeline([("prep", pre), ("clf", LogisticRegression(max_iter=500, class_weight="balanced"))]),
        "lightgbm": Pipeline([("prep", pre), ("clf", LGBMClassifier(class_weight="balanced", n_estimators=400, learning_rate=0.05, max_depth=6))]),
        "xgboost": Pipeline([("prep", pre), ("clf", XGBClassifier(scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1), eval_metric="logloss", n_estimators=400, learning_rate=0.05, max_depth=6))]),
    }

    best_model = None
    best_score = -1
    best_name = ""
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        report = classification_report(y_test, y_pred, digits=4, output_dict=True)
        f1_good = report["1"]["f1-score"]
        print(f"=== {name} ===")
        print(classification_report(y_test, y_pred, digits=4))
        print(confusion_matrix(y_test, y_pred))
        if f1_good > best_score:
            best_score = f1_good
            best_model = model
            best_name = name

    out_path = Path(args.model_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, out_path)
    print(f"[model] saved best ({best_name}) -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Train ML filter for MystriX")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="3m")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--dataset-out", default="ml_pipeline/data/divergence_dataset.csv")
    parser.add_argument("--dataset-in", default=None)
    parser.add_argument("--model-out", default="ml_pipeline/models/ml_filter.pkl")
    parser.add_argument("--stop-pct", type=float, default=0.03)
    parser.add_argument("--test-ratio", type=float, default=0.25)
    args = parser.parse_args()
    train_for_symbol(args)


if __name__ == "__main__":
    main()
