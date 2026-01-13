from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LiveScanRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])
    dataset_path: Optional[str] = None
    model_path: str = "ml_pipeline/models/ml_filter.pkl"
    threshold: float = 0.65
    max_events: int = 3


class DemoTradeRequest(BaseModel):
    symbol: str = "BNB/USDT"
    equity_pct: float = 0.005
    hold_seconds: int = 45
