from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, Tuple

from fastapi import APIRouter

from engine.bybit_data import BYBIT_MAINNET, fetch_ticker, fetch_tickers
from schemas.market import MarketPricesRequest


router = APIRouter(tags=["market"])

_CACHE: Dict[str, Dict[str, object]] = {}
_CACHE_TTL = 6


def _cache_key(base_url: str | None, category: str | None) -> str:
    base = (base_url or "").strip() or BYBIT_MAINNET
    cat = (category or "linear").strip().lower()
    return f"{base}|{cat}"


def _to_slash(sym: str) -> str:
    s = sym.upper()
    return f"{s[:-4]}/USDT" if s.endswith("USDT") and "/" not in s else s


def _normalize_symbols(symbols: list[str]) -> list[str]:
    out = []
    for sym in symbols:
        if not sym:
            continue
        out.append(_to_slash(str(sym).strip().upper()))
    return out


def _fetch_all_prices(base_url: str, category: str) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    tickers = fetch_tickers(category=category, base_url=base_url)
    for t in tickers:
        sym = _to_slash(str(t.get("symbol") or ""))
        if not sym:
            continue
        try:
            last = float(t.get("lastPrice") or 0.0)
        except (TypeError, ValueError):
            last = 0.0
        if last > 0:
            prices[sym] = last
    return prices


def _fetch_missing(symbols: list[str], base_url: str, category: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for sym in symbols:
        raw = sym.replace("/", "")
        ticker = fetch_ticker(raw, category=category, base_url=base_url)
        try:
            last = float(ticker.get("lastPrice") or 0.0)
        except (TypeError, ValueError):
            last = 0.0
        if last > 0:
            out[_to_slash(sym)] = last
    return out


@router.post("/market/prices")
def market_prices(req: MarketPricesRequest):
    symbols = _normalize_symbols(req.symbols)
    if not symbols:
        return {"prices": {}, "as_of": None, "count": 0}

    base_url = (req.base_url or "").strip() or BYBIT_MAINNET
    category = (req.category or "linear").strip().lower()
    key = _cache_key(base_url, category)
    now = time.time()
    cached = _CACHE.get(key, {})
    ts = float(cached.get("ts") or 0.0)
    prices = cached.get("prices")

    if not isinstance(prices, dict) or now - ts > _CACHE_TTL:
        prices = _fetch_all_prices(base_url, category)
        _CACHE[key] = {"ts": now, "prices": prices}

    out: Dict[str, float] = {}
    missing = []
    for sym in symbols:
        val = prices.get(sym) if isinstance(prices, dict) else None
        if val is None:
            missing.append(sym)
        else:
            out[sym] = float(val)

    if missing:
        extras = _fetch_missing(missing, base_url, category)
        if extras:
            out.update(extras)
            if isinstance(prices, dict):
                prices.update(extras)
                _CACHE[key] = {"ts": now, "prices": prices}

    stamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    return {"prices": out, "as_of": stamp, "count": len(out)}
