from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

import httpx

from settings import settings


def _now_utc() -> datetime:
    return datetime.utcnow()


class BaseProvider:
    async def fetch(self, symbols: List[str], start: datetime, end: datetime) -> List[Dict[str, Any]]:
        raise NotImplementedError


class NoopProvider(BaseProvider):
    async def fetch(self, symbols: List[str], start: datetime, end: datetime) -> List[Dict[str, Any]]:
        # Return a few synthetic articles centered around end time
        t0 = end - timedelta(hours=6)
        src = "LocalWire"
        sy = ",".join(symbols)
        return [
            {
                "id": f"noop-{i}",
                "title": f"{sy} market update #{i}",
                "source": src,
                "published_at": (t0 + timedelta(hours=i)).isoformat() + "Z",
                "url": None,
                "content": f"Synthetic article {i} on {sy}.",
            }
            for i in range(3)
        ]


class NewsAPIProvider(BaseProvider):
    BASE = "https://newsapi.org/v2/everything"

    async def fetch(self, symbols: List[str], start: datetime, end: datetime) -> List[Dict[str, Any]]:
        api_key = settings.NEWSAPI_KEY
        if not api_key:
            return []
        q = " OR ".join(set([s.replace("/", "") for s in symbols]))
        params = {
            "q": q,
            "from": start.isoformat(timespec="seconds"),
            "to": end.isoformat(timespec="seconds"),
            "sortBy": "relevancy",
            "language": "en",
            "pageSize": 50,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(self.BASE, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        out: List[Dict[str, Any]] = []
        for i, a in enumerate(data.get("articles", []) or []):
            out.append(
                {
                    "id": a.get("url", f"newsapi-{i}"),
                    "title": a.get("title") or "",
                    "source": (a.get("source") or {}).get("name", "NewsAPI"),
                    "published_at": a.get("publishedAt") or _now_utc().isoformat() + "Z",
                    "url": a.get("url"),
                    "content": a.get("content") or a.get("description") or "",
                }
            )
        return out


def get_provider() -> BaseProvider:
    prov = (settings.NEWS_PROVIDER or "none").lower()
    if prov == "newsapi":
        return NewsAPIProvider()
    # gdelt could be added similarly
    return NoopProvider()
