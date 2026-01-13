from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException

from engine.storage import resolve_db_path
from ml_pipeline.dataset_builder import build_dataset
from schemas.datasets import DatasetBuildRequest, StepBuildRequest
from utils.symbols import norm_symbol


router = APIRouter(tags=["datasets"])


@router.post("/datasets/build_concurrent")
def datasets_build(req: DatasetBuildRequest):
    if not req.symbols:
        raise HTTPException(status_code=400, detail="symbols list is empty")
    if len(req.symbols) > 30:
        raise HTTPException(status_code=400, detail="max 30 symbols supported in one request")
    try:
        frames = []
        per_symbol: Dict[str, int] = {}
        failed: List[str] = []
        messages: List[str] = []

        def log(msg: str):
            messages.append(msg)
            print(f"[BUILD_DATASET] {msg}")

        for idx, sym in enumerate(req.symbols):
            symbol = norm_symbol(sym)
            ok = False
            attempts = 3
            for attempt in range(1, attempts + 1):
                try:
                    log(f"{symbol}: fetch attempt {attempt}/{attempts}")
                    df = build_dataset(symbol, req.timeframe, req.start_date, req.end_date, stop_pct=req.stop_pct, target_pct=req.target_pct)
                    df["symbol"] = symbol
                    frames.append(df)
                    per_symbol[symbol] = len(df)
                    log(f"{symbol}: fetched {len(df)} rows")
                    ok = True
                    break
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc).lower()
                    if "429" in msg or "rate" in msg or "too many requests" in msg:
                        wait_s = 10 * attempt
                        log(f"{symbol}: rate limit hit, sleeping {wait_s}s before retry ({attempt}/{attempts})")
                        time.sleep(wait_s)
                        continue
                    # non-rate errors -> abort for this symbol
                    log(f"{symbol}: failed attempt {attempt}/{attempts} - {exc}")
                    break
            if not ok:
                failed.append(symbol)
            # gentle throttle between symbols
            if idx < len(req.symbols) - 1:
                time.sleep(0.35)

        if not frames:
            raise HTTPException(status_code=400, detail="No data fetched for requested symbols")
        out = pd.concat(frames, ignore_index=True)
        out_path = Path(req.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(out_path, index=False)
        return {
            "ok": True,
            "path": str(out_path),
            "rows": int(len(out)),
            "per_symbol": per_symbol,
            "failed": failed,
            "partial": bool(failed),
            "messages": messages,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/datasets/build_step")
def datasets_build_step(req: StepBuildRequest):
    """Build dataset for a single symbol, optionally appending to an existing CSV."""
    try:
        symbol = norm_symbol(req.symbol)
        out_path = Path(req.output_path)
        if req.truncate and out_path.exists():
            out_path.unlink()
        messages: List[str] = []
        cache_root = Path(req.cache_path).expanduser().resolve() if req.cache_path else None
        db_path = resolve_db_path(cache_root)
        messages.append(f"{symbol}: using cache db {db_path}")
        df = build_dataset(
            symbol,
            req.timeframe,
            req.start_date,
            req.end_date,
            stop_pct=req.stop_pct,
            target_pct=req.target_pct,
            log=messages,
            cache_root=cache_root,
        )
        df["symbol"] = symbol
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = not out_path.exists()
        df.to_csv(out_path, index=False, mode="a" if out_path.exists() else "w", header=header)
        return {"ok": True, "symbol": symbol, "rows": int(len(df)), "path": str(out_path), "messages": messages, "db_path": db_path}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
