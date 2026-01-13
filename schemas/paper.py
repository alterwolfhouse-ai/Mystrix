from __future__ import annotations

from pydantic import BaseModel


class PaperInitRequest(BaseModel):
    balance: float = 10000.0


class PaperOrderRequest(BaseModel):
    symbol: str
    side: str  # buy/sell
    size: float


class PaperCloseRequest(BaseModel):
    trade_id: int
