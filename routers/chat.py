from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List
import uuid

from fastapi import APIRouter, HTTPException

from schemas.chat import (
    ChatQuery, ChatResponse,
    SessionStartReq, SessionStartResp,
    SessionMsgReq, SessionMsgResp,
)
from schemas.news import NewsQuery
from services.market_data import get_bars, compute_features
from services.news_provider import get_provider
from services.news_normalizer import normalize_articles
from services.wizard_client import call_wizard_messages


router = APIRouter(prefix="/api", tags=["wizard-chat"])

# In-memory session store; process-lifetime only
_SESS: Dict[str, Dict] = {}


@router.post("/wizard/chat", response_model=ChatResponse)
async def wizard_chat(q: ChatQuery):
    try:
        now = datetime.now(timezone.utc)
        end = now
        start = end - timedelta(hours=q.hours)
        symbol = (q.symbols[0] if q.symbols else "BTC/USDT")

        # Bars + features snapshot
        df = get_bars(symbol, q.timeframe, start, end)
        bars = []
        if df is not None and not df.empty:
            last = min(len(df), q.lookback_bars)
            tail = df.tail(last)
            for idx, row in tail.iterrows():
                bars.append({
                    "t": idx.isoformat(),
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "v": float(row.get("volume", 0.0)),
                })
        feats = compute_features(df)

        # Optional news
        news_items = []
        if q.include_news:
            nq = NewsQuery(
                symbols=q.symbols or [symbol],
                timeframe=q.timeframe,
                start=start,
                end=end,
                news_window_h=q.hours,
                lookback_bars=q.lookback_bars,
                top_k=q.top_k,
            )
            provider = get_provider()
            raw = await provider.fetch(nq.symbols, nq.start, nq.end)
            items = normalize_articles(raw, nq)[: max(1, min(q.top_k, 5))]
            news_items = [i.dict() for i in items]

        # Compose messages for the LLM
        sys_msg = {
            "role": "system",
            "content": (
                "You are MystriX's Market & Technical Analyst.\n"
                "Constraints: Base your report ONLY on supplied BARS/FEATURES and NEWS.\n"
                "Deliver a professional, concrete, data-referenced market brief.\n"
                "Length: between {minw} and {maxw} words.\n"
                "Structure with short headings and readable paragraphs.\n"
                "Do not make price predictions; discuss scenarios and invalidation levels.\n"
            ).format(minw=q.words_min, maxw=q.words_max),
        }
        user_payload = {
            "user_request": q.message,
            "symbols": q.symbols or [symbol],
            "timeframe": q.timeframe,
            "bars_tail": bars[-300:],  # keep prompt compact
            "features": feats,
            "news": news_items,
            "task": [
                "Write a market & technical analysis brief (trend, momentum, volatility)",
                "Reference RSI/MACD/ATR/ROC values where useful",
                "Tie NEWS timing to bars when relevant",
                "Provide 2–3 scenarios and invalidation cues",
                "End with actionable watchpoints (non-advisory)",
            ],
        }
        user_msg = {"role": "user", "content": str(user_payload)}

        # Run LLM
        out = call_wizard_messages([sys_msg, user_msg], options={"temperature": 0.6, "num_predict": 1024})

        return ChatResponse(
            symbols=q.symbols or [symbol],
            timeframe=q.timeframe,
            generated_at=now,
            words_target=[q.words_min, q.words_max],
            report_markdown=out,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/wizard/session/start", response_model=SessionStartResp)
async def wizard_session_start(req: SessionStartReq):
    try:
        now = datetime.now(timezone.utc)
        sym = (req.symbols[0] if req.symbols else "BTC/USDT")
        # Market window: months_market back from now
        end = now
        start_mkt = end - timedelta(days=int(req.months_market * 30))
        # News window: years_news back from now
        start_news = end - timedelta(days=int(req.years_news * 365))

        # Bars + features snapshot (larger lookback for context)
        df = get_bars(sym, req.timeframe, start_mkt, end)
        bars_tail: List[Dict] = []
        if df is not None and not df.empty:
            last = min(len(df), req.lookback_bars)
            tail = df.tail(last)
            for idx, row in tail.iterrows():
                bars_tail.append({
                    "t": idx.isoformat(),
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "v": float(row.get("volume", 0.0)),
                })
        feats = compute_features(df)

        news_items: List[Dict] = []
        if req.include_news and req.years_news > 0:
            nq = NewsQuery(
                symbols=req.symbols or [sym],
                timeframe=req.timeframe,
                start=start_news,
                end=end,
                news_window_h=int(req.years_news * 365 * 24),
                lookback_bars=req.lookback_bars,
                top_k=5,
            )
            provider = get_provider()
            raw = await provider.fetch(nq.symbols, nq.start, nq.end)
            items = normalize_articles(raw, nq)[:5]
            news_items = [i.dict() for i in items]

        # Minimal fundamentals/vision stubs (can be replaced with real providers later)
        fundamentals = {
            "note": "Fundamentals provider not configured; using technical snapshot only.",
        }

        sess_id = uuid.uuid4().hex
        _SESS[sess_id] = {
            "created_at": now.isoformat(),
            "symbols": req.symbols or [sym],
            "timeframe": req.timeframe,
            "bars_tail": bars_tail[-1200:],
            "features": feats,
            "news": news_items,
            "fundamentals": fundamentals,
            "history": [],  # store short chat history for continuity
        }
        return SessionStartResp(
            session_id=sess_id,
            symbols=req.symbols or [sym],
            timeframe=req.timeframe,
            prepared={
                "bars": len(bars_tail),
                "news": len(news_items),
                "features": list(feats.keys()),
            },
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/wizard/session/message", response_model=SessionMsgResp)
async def wizard_session_message(req: SessionMsgReq):
    try:
        sess = _SESS.get(req.session_id)
        if not sess:
            raise HTTPException(404, "session not found")
        now = datetime.now(timezone.utc)
        # Compose persona + context once
        sys_msg = {
            "role": "system",
            "content": (
                "You are MystriX, a concise, no-nonsense Market & Technical Analyst.\n"
                "Use ONLY the provided CONTEXT (bars, features, news, fundamentals).\n"
                "Write in a crisp, professional tone with headings: Pulse, Structure, Drivers, Scenarios, Invalidation, Watchlist.\n"
                "Avoid generic tutorials or repeating the raw context.\n"
            ),
        }
        context_payload = {
            "symbols": sess.get("symbols"),
            "timeframe": sess.get("timeframe"),
            "bars_tail": sess.get("bars_tail", [])[-300:],
            "features": sess.get("features", {}),
            "news": sess.get("news", []),
            "fundamentals": sess.get("fundamentals", {}),
        }
        context_msg = {"role": "system", "content": str(context_payload)}
        messages = [sys_msg, context_msg]
        # short rolling history to keep continuity
        for past in sess.get("history", [])[-6:]:
            messages.append({"role": "user", "content": past.get("user")})
            messages.append({"role": "assistant", "content": past.get("bot")})
        messages.append({"role": "user", "content": req.message})

        out = call_wizard_messages(messages, options={"temperature": 0.6, "num_predict": 1200})
        sess.setdefault("history", []).append({"user": req.message, "bot": out})

        return SessionMsgResp(session_id=req.session_id, generated_at=now, report_markdown=out)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
