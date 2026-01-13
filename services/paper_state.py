from __future__ import annotations

import random
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

_PAPER_LOCK = threading.RLock()
_PAPER_STATE: Dict[str, Any] = {
    "balance": 10000.0,
    "active": [],
    "history": [],
    "next_id": 1,
    "prices": {},  # symbol -> last price
}


def reset(balance: float = 10000.0) -> float:
    with _PAPER_LOCK:
        _PAPER_STATE.clear()
        _PAPER_STATE.update(
            {
                "balance": float(balance),
                "active": [],
                "history": [],
                "next_id": 1,
                "prices": {},
            }
        )
        return _PAPER_STATE["balance"]


def snapshot() -> Dict[str, Any]:
    with _PAPER_LOCK:
        return {
            "balance": _PAPER_STATE["balance"],
            "active": list(_PAPER_STATE["active"]),
            "history": list(_PAPER_STATE["history"]),
            "prices": dict(_PAPER_STATE.get("prices", {})),
        }


def paper_price(symbol: str) -> float:
    with _PAPER_LOCK:
        prices = _PAPER_STATE.setdefault("prices", {})
        if symbol not in prices:
            prices[symbol] = random.uniform(90, 110)
        return float(prices[symbol])


def paper_step(symbols: Optional[List[str]] = None) -> Dict[str, float]:
    updated: Dict[str, float] = {}
    with _PAPER_LOCK:
        prices = _PAPER_STATE.setdefault("prices", {})
        if symbols is None or not symbols:
            symbols = list(prices.keys()) + [t["symbol"] for t in _PAPER_STATE.get("active", [])]
            symbols = list(set(symbols))
        for sym in symbols:
            last = prices.get(sym, random.uniform(90, 110))
            shock = random.uniform(-0.005, 0.005)
            new_price = max(0.01, last * (1 + shock))
            prices[sym] = new_price
            updated[sym] = new_price
    return updated


def open_order(symbol: str, side: str, size: float) -> Dict[str, Any]:
    price = paper_price(symbol)
    with _PAPER_LOCK:
        tid = _PAPER_STATE["next_id"]
        _PAPER_STATE["next_id"] += 1
        trade = {
            "id": tid,
            "symbol": symbol,
            "side": side.lower(),
            "size": float(size),
            "status": "open",
            "opened_at": datetime.utcnow().isoformat(),
            "entry_price": price,
            "exit_price": None,
            "pnl": 0.0,
            "ret_pct": 0.0,
        }
        _PAPER_STATE["active"].append(trade)
        return trade


def close_order(trade_id: int) -> Dict[str, Any]:
    with _PAPER_LOCK:
        active = _PAPER_STATE["active"]
        trade = next((t for t in active if t.get("id") == trade_id), None)
        if not trade:
            raise KeyError("trade not found")
        price = paper_step([trade["symbol"]]).get(trade["symbol"], paper_price(trade["symbol"]))
        entry = float(trade.get("entry_price", price))
        side = trade.get("side", "buy")
        ret = (price - entry) / entry if side == "buy" else (entry - price) / entry
        pnl = ret * float(trade.get("size", 0.0))
        _PAPER_STATE["balance"] += pnl
        active.remove(trade)
        trade["status"] = "closed"
        trade["closed_at"] = datetime.utcnow().isoformat()
        trade["exit_price"] = price
        trade["ret_pct"] = ret * 100
        trade["pnl"] = pnl
        _PAPER_STATE["history"].append(trade)
        return trade


def tick(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    updated = paper_step(symbols)
    closed: List[Dict[str, Any]] = []
    with _PAPER_LOCK:
        still_active = []
        for t in _PAPER_STATE["active"]:
            sym = t["symbol"]
            price = updated.get(sym, paper_price(sym))
            entry = float(t.get("entry_price", price))
            side = t.get("side", "buy")
            ret = (price - entry) / entry if side == "buy" else (entry - price) / entry
            if abs(ret) >= 0.01:
                pnl = ret * float(t.get("size", 0.0))
                _PAPER_STATE["balance"] += pnl
                t["status"] = "closed"
                t["closed_at"] = datetime.utcnow().isoformat()
                t["exit_price"] = price
                t["ret_pct"] = ret * 100
                t["pnl"] = pnl
                _PAPER_STATE["history"].append(t)
                closed.append(t)
            else:
                still_active.append(t)
        _PAPER_STATE["active"] = still_active
        return {
            "updated": updated,
            "closed": closed,
            "balance": _PAPER_STATE["balance"],
        }
