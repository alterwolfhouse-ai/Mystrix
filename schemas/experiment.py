from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExperimentRunRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])
    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    timeframe: str = "3m"
    threshold: float = 0.65
    equity_risk: float = 0.02
    initial_capital: float = 10_000.0
    dataset_path: Optional[str] = "ml_pipeline/data/div_all_3m.csv"
    model_path: str = "ml_pipeline/models/ml_filter.pkl"
    stop_pct: float = 0.03
    target_pct: float = 0.015
    holding_minutes_hint: float = 0.0
    log_name: Optional[str] = None
    log_skipped: bool = False


class ExperimentFetchRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "3m"
    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    dataset_path: Optional[str] = None
    stop_pct: float = 0.03
    target_pct: float = 0.015
