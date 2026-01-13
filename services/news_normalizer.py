from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List
import hashlib

import pandas as pd

from schemas.news import NewsItem, Sentiment, TimeAlignment, NewsQuery
from utils.cache import global_cache
from services.market_data import get_bars
from services.wizard_client import call_wizard


def summarize_1s(text: str) -> str:
    key = ("sum1s", hashlib.sha1(text.encode("utf-8")).hexdigest())
    cached = global_cache.get(key)
    if cached:
        return cached
    # Try local LLM (short prompt), else simple heuristic
    try:
        prompt = f"Summarize in one sentence, plain English, <= 25 words.\nTEXT:\n{text[:2000]}"
        s = call_wizard(prompt)
        s = (s or "").split("\n")[0].strip()
        if not s:
            raise RuntimeError
    except Exception:
        s = (text or "").strip()
        if len(s) > 160:
            s = s[:157] + "..."
    global_cache.set(key, s)
    return s


def score_sentiment(text: str) -> Sentiment:
    t = (text or "").lower()
    neg = sum(x in t for x in ["falls", "bear", "hack", "lawsuit", "ban", "down", "drop", "fraud", "risk"])
    pos = sum(x in t for x in ["rally", "up", "bull", "partnership", "launch", "upgrade", "support", "growth"])
    polarity = (pos - neg) / max(1, pos + neg)
    confidence = min(1.0, 0.6 + 0.1 * (pos + neg))
    return Sentiment(polarity=float(polarity), confidence=float(confidence))


def compute_relevance(article: Dict, symbols: List[str], question: str | None) -> float:
    score = 0.0
    title = (article.get("title") or "").upper()
    content = (article.get("content") or "").upper()
    for s in symbols:
        key = s.replace("/", "")
        if key in title:
            score += 0.4
        if key in content:
            score += 0.3
    if question:
        q = question.upper()
        if any(w in content for w in q.split()[:5]):
            score += 0.2
    return max(0.0, min(1.0, score))


def dedupe_cluster(articles: List[Dict]) -> List[Dict]:
    groups = {}
    for a in articles:
        ts = pd.to_datetime(a.get("published_at"))
        key = (a.get("title", "").strip().lower()[:40], ts.floor("2H"))
        groups.setdefault(key, []).append(a)
    out = []
    for key, items in groups.items():
        # choose highest credibility if present, else first
        best = sorted(items, key=lambda x: float(x.get("credibility", 0.8)), reverse=True)[0]
        best["dedupe_group"] = hashlib.md5(str(key).encode()).hexdigest()
        out.append(best)
    return out


def align_to_bars(article_ts: datetime, ohlcv: pd.DataFrame, timeframe: str) -> TimeAlignment | None:
    if ohlcv is None or ohlcv.empty:
        return None
    ts = pd.to_datetime(article_ts)
    idx = ohlcv.index
    nearest_idx = idx.get_indexer([ts], method="nearest")[0]
    nearest_ts = idx[nearest_idx]
    # 30m move and 20-bar volume spike
    look = int(pd.Timedelta("30min") / (idx[1] - idx[0])) if len(idx) > 1 else 10
    j = min(len(idx) - 1, nearest_idx + look)
    price_move = (float(ohlcv["close"].iloc[j]) / float(ohlcv["close"].iloc[nearest_idx]) - 1.0) * 100.0
    vol_win = ohlcv["volume"].rolling(20).mean()
    vol_spike = float((ohlcv["volume"].iloc[nearest_idx] / (vol_win.iloc[nearest_idx] + 1e-9)))
    return TimeAlignment(
        closest_bar_ts=pd.Timestamp(nearest_ts).to_pydatetime(),
        bar_offset_min=int((nearest_ts - ts).total_seconds() / 60.0),
        price_move_30m=float(price_move),
        volume_spike=float(vol_spike),
    )


def normalize_articles(raw: List[Dict], query: NewsQuery) -> List[NewsItem]:
    # Fetch bars once for alignment (first symbol as reference)
    df = get_bars(query.symbols[0], query.timeframe, query.start, query.end)
    items: List[NewsItem] = []
    for a in raw:
        try:
            text = (a.get("content") or a.get("title") or "")
            summ = summarize_1s(text)
            sent = score_sentiment(text)
            rel = compute_relevance(a, query.symbols, query.user_question)
            ts = pd.to_datetime(a.get("published_at"))
            align = align_to_bars(ts, df, query.timeframe)
            stance = (
                "positive" if sent.polarity > 0.35 else
                "slightly-positive" if sent.polarity > 0.1 else
                "slightly-negative" if sent.polarity < -0.1 else
                "negative" if sent.polarity < -0.35 else "neutral"
            )
            items.append(
                NewsItem(
                    id=str(a.get("id", "")),
                    title=a.get("title", ""),
                    source=a.get("source", "news"),
                    published_at=ts.to_pydatetime(),
                    url=a.get("url"),
                    entities=[],
                    tickers=[s.replace("/", "") for s in query.symbols],
                    topic_labels=[],
                    summary_1s=summ,
                    stance=stance,
                    sentiment=sent,
                    relevance=float(rel),
                    time_alignment=align,
                    credibility=float(a.get("credibility", 0.8)),
                    dedupe_group=None,
                )
            )
        except Exception:
            continue
    # dedupe and sort by relevance desc then recency
    deduped = dedupe_cluster([i.dict() for i in items])
    deduped_items = [NewsItem(**d) for d in deduped]
    deduped_items.sort(key=lambda x: (float(x.relevance), x.published_at), reverse=True)
    return deduped_items
