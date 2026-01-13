from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException

from schemas.news import NewsEnvelope, NewsItem, NewsQuery
from services.news_provider import get_provider
from services.news_normalizer import normalize_articles
from services.market_data import get_bars, compute_features
from services.wizard_client import compose_prompt, call_wizard


router = APIRouter(prefix="/api", tags=["news"])


@router.post("/news/normalize", response_model=NewsEnvelope)
async def news_normalize(q: NewsQuery):
    try:
        provider = get_provider()
        raw = await provider.fetch(q.symbols, q.start, q.end)
        items = normalize_articles(raw, q)
        items = items[: max(1, min(q.top_k or 5, 5))]
        env = NewsEnvelope(
            symbols=q.symbols,
            timeframe=q.timeframe,
            lookback_bars=q.lookback_bars,
            news_window_h=q.news_window_h,
            news_items=items,
            known_future_events=[],
            user_question=q.user_question,
        )
        return env
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/wizard/analyze")
async def wizard_analyze(env: NewsEnvelope) -> Dict[str, str]:
    try:
        sym = env.symbols[0]
        # bars snapshot for prompt (last N bars)
        end = datetime.utcnow()
        start = end - (end - end)
        df = get_bars(sym, env.timeframe, end - (end - end), end)
        if df is None:
            bars = []
        else:
            bars = [
                {
                    "t": idx.isoformat(),
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "v": float(row["volume"]),
                }
                for idx, row in df.tail(min(len(df), max(100, env.lookback_bars))).iterrows()
            ]
        feats = compute_features(df)
        prompt = compose_prompt({"bars_tail": bars[-50:]}, feats, env.dict())
        out = call_wizard(prompt)
        return {"report_markdown": out}
    except Exception as e:
        raise HTTPException(500, str(e))
