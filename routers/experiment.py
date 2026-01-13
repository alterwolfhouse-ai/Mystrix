from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException

from experiment.plus_runner import PlusExperimentConfig, run_experiment
from ml_pipeline.dataset_builder import build_dataset
from schemas.experiment import ExperimentFetchRequest, ExperimentRunRequest


router = APIRouter(tags=["experiment"])


@router.post("/experiment/run_plus")
def experiment_run(req: ExperimentRunRequest):
    try:
        cfg = PlusExperimentConfig(
            symbols=req.symbols or ["BTC/USDT"],
            start_date=req.start_date,
            end_date=req.end_date,
            dataset_path=req.dataset_path,
            model_path=req.model_path,
            ml_threshold=req.threshold,
            equity_risk=req.equity_risk,
            initial_capital=req.initial_capital,
            stop_pct=req.stop_pct,
            target_pct=req.target_pct,
            holding_minutes_hint=req.holding_minutes_hint,
            log_skipped=req.log_skipped,
            timeframe=req.timeframe,
        )
        trades_df, summary, series = run_experiment(cfg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Experiment failed: {exc}")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_name = req.log_name or f"run_{ts}.csv"
    log_path = Path("experiment/logs") / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(log_path, index=False)
    summary = dict(summary)
    summary["log_path"] = str(log_path)
    summary["log_name"] = log_name
    preview = trades_df[trades_df["status"] == "taken"].copy()
    preview = preview.sort_values("entry_time").reset_index(drop=True)
    for col in ("entry_time", "exit_time"):
        if col in preview.columns:
            preview[col] = preview[col].astype(str)
    preview_records = preview.to_dict(orient="records")
    return {"summary": summary, "trades_preview": preview_records, "series": series}


@router.get("/experiment/dataset_stats")
def experiment_dataset_stats(dataset_path: str = "ml_pipeline/data/div_all_3m.csv"):
    ds_path = Path(dataset_path)
    if not ds_path.exists():
        raise HTTPException(status_code=404, detail=f"dataset not found: {dataset_path}")
    try:
        df = pd.read_csv(ds_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to read dataset: {exc}")
    total = int(len(df))
    good = int(df["label"].sum()) if "label" in df.columns else 0
    bad = total - good
    symbol_stats: Dict[str, Dict[str, int]] = {}
    if "symbol" in df.columns:
        grouped = df.groupby("symbol")
        for sym, grp in grouped:
            rows = int(len(grp))
            good_rows = int(grp["label"].sum()) if "label" in grp.columns else 0
            symbol_stats[str(sym)] = {
                "rows": rows,
                "good": good_rows,
                "bad": rows - good_rows,
            }
    updated = datetime.utcfromtimestamp(ds_path.stat().st_mtime).isoformat() + "Z"
    return {
        "dataset_path": str(ds_path),
        "total_rows": total,
        "good_labels": good,
        "bad_labels": bad,
        "symbols": symbol_stats,
        "updated_at": updated,
    }


@router.post("/experiment/fetch_dataset")
def experiment_fetch_dataset(req: ExperimentFetchRequest):
    try:
        symbols = [s.strip() for s in req.symbols if s.strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        frames = []
        stats: Dict[str, Dict[str, int]] = {}
        for sym in symbols:
            df = build_dataset(sym, req.timeframe, req.start_date, req.end_date, stop_pct=req.stop_pct, target_pct=req.target_pct)
            good = int(df["label"].sum()) if "label" in df.columns else 0
            stats[sym] = {"rows": int(len(df)), "good": good, "bad": int(len(df)) - good}
            if not df.empty:
                frames.append(df)
        if not frames:
            raise HTTPException(status_code=400, detail="No trades returned for requested parameters")
        merged = pd.concat(frames, ignore_index=True)
        default_name = f"div_exp_{symbols[0].replace('/', '').lower()}_{req.timeframe}_{int(datetime.utcnow().timestamp())}.csv"
        dataset_path = Path(req.dataset_path) if req.dataset_path else Path("ml_pipeline/data") / default_name
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(dataset_path, index=False)
        return {
            "dataset_path": str(dataset_path),
            "rows": int(len(merged)),
            "symbols": stats,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"dataset fetch failed: {exc}")
