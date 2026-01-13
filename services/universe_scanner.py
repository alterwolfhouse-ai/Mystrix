from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from engine.bybit_data import BYBIT_MAINNET, fetch_tickers

_CACHE: Dict[str, Any] = {"ts": 0.0, "suggestions": [], "meta": {}}
_CACHE_TTL = 300  # seconds


def _num(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [0.0 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]


def _to_slash(sym: str) -> str:
    s = sym.upper()
    if s.endswith("USDT") and "/" not in s:
        return f"{s[:-4]}/USDT"
    return s


def universe_suggestions(limit: int = 12, base_url: str = BYBIT_MAINNET) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    now = time.time()
    if _CACHE["suggestions"] and now - float(_CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["suggestions"][:limit], _CACHE.get("meta", {})

    tickers = fetch_tickers(category="linear", base_url=base_url)
    candidates = []
    for t in tickers:
        sym = str(t.get("symbol") or "")
        if not sym.endswith("USDT") or "-" in sym:
            continue
        last = _num(t.get("lastPrice"))
        high = _num(t.get("highPrice24h"))
        low = _num(t.get("lowPrice24h"))
        turnover = _num(t.get("turnover24h"))
        change = _num(t.get("price24hPcnt"))
        if last <= 0 or high <= 0 or low <= 0 or turnover <= 0:
            continue
        range_pct = (high - low) / last
        candidates.append(
            {
                "symbol": _to_slash(sym),
                "turnover": turnover,
                "range_pct": range_pct,
                "change_abs": abs(change),
            }
        )

    if not candidates:
        return [], {"as_of": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(), "count": 0}

    range_vals = [c["range_pct"] for c in candidates]
    change_vals = [c["change_abs"] for c in candidates]
    turnover_vals = [math.log10(c["turnover"] + 1.0) for c in candidates]
    range_norm = _normalize(range_vals)
    change_norm = _normalize(change_vals)
    turnover_norm = _normalize(turnover_vals)

    scored: List[Dict[str, Any]] = []
    for idx, c in enumerate(candidates):
        score = (
            0.5 * range_norm[idx]
            + 0.3 * change_norm[idx]
            + 0.2 * turnover_norm[idx]
        )
        scored.append(
            {
                "symbol": c["symbol"],
                "score": round(score, 4),
                "range_pct": round(c["range_pct"] * 100, 2),
                "change_pct": round(c["change_abs"] * 100, 2),
                "turnover": round(c["turnover"], 2),
            }
        )

    scored.sort(key=lambda s: s["score"], reverse=True)
    meta = {
        "as_of": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "count": len(scored),
        "ttl_s": _CACHE_TTL,
    }
    _CACHE["ts"] = now
    _CACHE["suggestions"] = scored
    _CACHE["meta"] = meta
    return scored[:limit], meta
