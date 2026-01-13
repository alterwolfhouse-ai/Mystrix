#!/usr/bin/env python3
"""Build divergence datasets for multiple symbols and combine."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd

from ml_pipeline.dataset_builder import build_dataset  # type: ignore


def main():
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    timeframe = "3m"
    start_date = "2020-01-01"
    out_dir = Path("ml_pipeline/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = []
    for sym in symbols:
        df = build_dataset(sym, timeframe, start_date)
        filename = f"div_{sym.replace('/', '').lower()}_{timeframe}.csv"
        path = out_dir / filename
        df.to_csv(path, index=False)
        combined.append(df)
        print(f"[saved] {sym} -> {path}")
    merged = pd.concat(combined, ignore_index=True)
    merged_path = out_dir / f"div_all_{timeframe}.csv"
    merged.to_csv(merged_path, index=False)
    print(f"[saved] combined dataset -> {merged_path} rows={len(merged)}")


if __name__ == "__main__":
    main()
