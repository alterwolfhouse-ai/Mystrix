"""Runtime ML filter used by MystriX."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import joblib
import numpy as np
import pandas as pd


@dataclass
class MLFilterResult:
    action: str
    confidence: float
    risk_multiplier: float
    notes: str


class MLFilter:
    def __init__(self, model_path: Path):
        self.model = joblib.load(model_path)
        self.num_cols = [
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
        self.cat_cols = ["symbol"]
        self.all_cols = self.num_cols + self.cat_cols

    def score(self, features: Dict[str, Any], threshold: float = 0.5) -> MLFilterResult:
        row = {col: features.get(col) for col in self.all_cols}
        df = pd.DataFrame([row])
        prob = float(self.model.predict_proba(df)[0, 1])
        action = "take" if prob >= threshold else "skip"
        risk_multiplier = np.interp(prob, [threshold, 1.0], [0.75, 1.25]) if action == "take" else 0.0
        notes = f"prob={prob:.3f}"
        return MLFilterResult(action=action, confidence=prob, risk_multiplier=risk_multiplier, notes=notes)

    def batch_probabilities(self, dataset: pd.DataFrame) -> np.ndarray:
        subset = dataset[self.all_cols].copy()
        probs = self.model.predict_proba(subset)[:, 1]
        return probs
