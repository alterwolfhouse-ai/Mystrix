from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl, Field


class Sentiment(BaseModel):
    polarity: float  # -1..1
    confidence: float  # 0..1


class TimeAlignment(BaseModel):
    closest_bar_ts: datetime
    bar_offset_min: int
    price_move_30m: float
    volume_spike: float


class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    published_at: datetime
    url: Optional[HttpUrl] = None
    entities: List[str] = []
    tickers: List[str] = []
    topic_labels: List[str] = []
    summary_1s: str
    stance: Literal[
        "negative",
        "slightly-negative",
        "neutral",
        "slightly-positive",
        "positive",
    ] = "neutral"
    sentiment: Sentiment
    relevance: float = Field(ge=0, le=1)
    time_alignment: Optional[TimeAlignment] = None
    credibility: float = Field(ge=0, le=1, default=0.8)
    dedupe_group: Optional[str] = None


class NewsQuery(BaseModel):
    symbols: List[str]
    timeframe: str  # e.g., "15m"
    start: datetime
    end: datetime
    news_window_h: int = 72
    lookback_bars: int = 500
    user_question: Optional[str] = None
    top_k: int = 5


class NewsEnvelope(BaseModel):
    symbols: List[str]
    timeframe: str
    lookback_bars: int
    news_window_h: int
    news_items: List[NewsItem]
    known_future_events: List[dict] = []
    user_question: Optional[str] = None
