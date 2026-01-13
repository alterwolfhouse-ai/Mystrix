from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatQuery(BaseModel):
    message: str = Field(..., description="User natural language request")
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])  # default universe head
    timeframe: str = Field(default="3m")
    hours: int = Field(default=24, ge=1, le=24*14)
    lookback_bars: int = Field(default=600, ge=50, le=5000)
    include_news: bool = Field(default=True)
    top_k: int = Field(default=5, ge=1, le=5)
    words_min: int = Field(default=500, ge=200, le=1500)
    words_max: int = Field(default=1000, ge=300, le=2500)


class ChatResponse(BaseModel):
    symbols: List[str]
    timeframe: str
    generated_at: datetime
    words_target: List[int]
    report_markdown: str


# Sessioned chat (context prepared once)
class SessionStartReq(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = Field(default="3m")
    months_market: int = Field(default=2, ge=1, le=36)
    years_news: int = Field(default=2, ge=0, le=10)
    include_news: bool = True
    lookback_bars: int = Field(default=1200, ge=200, le=10000)


class SessionStartResp(BaseModel):
    session_id: str
    symbols: List[str]
    timeframe: str
    prepared: dict


class SessionMsgReq(BaseModel):
    session_id: str
    message: str


class SessionMsgResp(BaseModel):
    session_id: str
    generated_at: datetime
    report_markdown: str
