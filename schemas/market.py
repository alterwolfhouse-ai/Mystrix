from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MarketPricesRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    base_url: Optional[str] = None
    category: Optional[str] = "linear"
