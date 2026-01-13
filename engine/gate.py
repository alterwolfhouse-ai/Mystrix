"""
8h Gate scanner

Ranks symbols cross‑sectionally using 8h volume ROC and simple quality checks.
Composite score = 0.7 * vroc_pct + 0.3 * checks, where checks aggregates
placeholder features (RSI, momentum, liquidity).

Persist the latest ranked list in derived_info['gate_snapshot'].
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import pandas as pd

from .storage import raw_ohlcv, resample, save_derived, load_derived
from .indicators import rsi_wilder


@dataclass
class GateConfig:
    threshold: float = 0.65
    vroc_weight: float = 0.7
    checks_weight: float = 0.3
    base_tf: str = '1h'
    vroc_span: int = 8
    # Inner weights for checks block (normalized runtime)
    w_oi: float = 0.25
    w_rsi: float = 0.20
    w_mom: float = 0.25
    w_greed: float = 0.15
    w_hype: float = 0.15


class GateScanner:
    def __init__(self, cfg: GateConfig | None = None):
        self.cfg = cfg or GateConfig()

    def scan(self, symbols: List[str], base_tf: str = "1h") -> List[Dict]:
        rows = []
        base_tf = base_tf or self.cfg.base_tf
        # Build 8H bars from RAW base timeframe
        for sym in symbols:
            df = raw_ohlcv(sym, base_tf)
            if df.empty:
                continue
            d8 = resample(df, "8H")
            if len(d8) < 20:
                continue
            vol = d8["volume_quote"].astype(float)
            ema = vol.ewm(span=max(1,int(self.cfg.vroc_span)), adjust=False).mean()
            vroc_raw = (vol / ema.replace(0, np.nan)) - 1.0
            vroc_raw = vroc_raw.fillna(0.0)
            # Checks block (0..1). OI/Greed/Hype placeholders for now
            rsi = rsi_wilder(d8['close'], 14).fillna(50)
            rsi_q = 1 - np.minimum(1.0, np.abs(rsi - 50) / 50)  # neutral near 50
            mom = (d8['close'].pct_change().rolling(8).mean()).fillna(0)
            mom_q = (mom - mom.min()) / (mom.max() - mom.min() + 1e-9)
            oi_q = 0.0
            greed_q = 0.0
            hype_q = 0.0
            wsum = max(1e-9, (self.cfg.w_oi + self.cfg.w_rsi + self.cfg.w_mom + self.cfg.w_greed + self.cfg.w_hype))
            chk = (
                self.cfg.w_oi*oi_q +
                self.cfg.w_rsi*float(rsi_q.iloc[-1]) +
                self.cfg.w_mom*float(mom_q.iloc[-1]) +
                self.cfg.w_greed*greed_q +
                self.cfg.w_hype*hype_q
            ) / wsum
            rows.append({
                "symbol": sym,
                "vroc_raw": float(vroc_raw.iloc[-1]),
                "checks": float(chk),
                "ts": int(d8.index[-1].timestamp() * 1000),
            })

        if not rows:
            snap = {"symbols": [], "ts": 0}
            save_derived("gate_snapshot", json.dumps(snap))
            return []

        # Cross‑sectional percentile on vroc_raw
        v = np.array([r["vroc_raw"] for r in rows], dtype=float)
        order = v.argsort()
        pct = np.empty_like(order, dtype=float)
        pct[order] = np.linspace(0, 1, num=len(v))
        for i, r in enumerate(rows):
            r["vroc_pct"] = float(pct[i])
            score = self.cfg.vroc_weight * r["vroc_pct"] + self.cfg.checks_weight * r["checks"]
            r["score"] = float(max(0.0, min(1.0, score)))

        rows.sort(key=lambda x: x["score"], reverse=True)
        snap = {"symbols": rows, "ts": max(r["ts"] for r in rows)}
        save_derived("gate_snapshot", json.dumps(snap))
        return rows

    def snapshot(self) -> Dict:
        raw = load_derived("gate_snapshot")
        if not raw:
            return {"symbols": [], "ts": 0}
        try:
            return json.loads(raw)
        except Exception:
            return {"symbols": [], "ts": 0}


