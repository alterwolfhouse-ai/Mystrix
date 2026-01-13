from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class DatasetBuildRequest(BaseModel):
    symbols: List[str]
    timeframe: str = "3m"
    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    stop_pct: float = 0.03
    target_pct: float = 0.015
    output_path: str = "ml_pipeline/data/div_custom.csv"


class StepBuildRequest(BaseModel):
    symbol: str
    timeframe: str = "3m"
    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    stop_pct: float = 0.03
    target_pct: float = 0.015
    output_path: str = "ml_pipeline/data/div_custom.csv"
    truncate: bool = False
    cache_path: Optional[str] = None
