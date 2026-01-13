from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestReq(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])
    start: str
    end: str
    overrides: Dict[str, Any] = Field(default_factory=dict)  # timeframe_hist and Pine params
    engine: str = Field(default="long")  # long|short|both


class ConcurrentBacktestRequest(BaseModel):
    dataset_path: str = "ml_pipeline/data/div_all_3m.csv"
    model_path: Optional[str] = "ml_pipeline/models/ml_filter.pkl"
    threshold: float = 0.65
    symbols: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_equity: float = 10_000.0
    equity_pct: float = 0.5
    fee_bps: float = 5.0
    max_positions: int = 20
    max_assets: int = 20


class DeepBacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "3m"
    overrides: Dict[str, Any] = Field(default_factory=dict)
    start: Optional[str] = None
    end: Optional[str] = None
    engine: str = Field(default="long")
