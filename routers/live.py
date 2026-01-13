from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from schemas.live import DemoTradeRequest, LiveScanRequest
from services.live_feed import detect_live_divergences
from services.live_state import drain_demo_events, queue_demo_event, set_live_heartbeat
from engine.bybit_data import fetch_klines, BYBIT_MAINNET


router = APIRouter(tags=["live"])


@router.post("/live/scan")
def live_scan(req: LiveScanRequest):
    try:
        events = detect_live_divergences(
            symbols=req.symbols,
            model_path=req.model_path,
            threshold=req.threshold,
            timeframe="3m",
            max_events=None,  # scan all; no cap
        )
        demo_events = drain_demo_events()
        if demo_events:
            events.extend(demo_events)
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        set_live_heartbeat(now)
        print(f"[LIVE_HEARTBEAT] {now.isoformat()} | assets={len(req.symbols)} events={len(events)}")
        return {
            "events": events,
            "heartbeat": now.isoformat(),
            "scan_count": len(events),
            "symbols": req.symbols,
        }
    except Exception as exc:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        return {
            "events": [],
            "heartbeat": now.isoformat(),
            "scan_count": 0,
            "symbols": req.symbols,
            "error": str(exc),
        }


def _schedule_demo_close(trade: Dict[str, Any], hold_seconds: int) -> None:
    def _complete() -> None:
        exit_price = float(trade["entry_price"]) * (1 + random.uniform(-0.01, 0.01))
        pnl = trade["trade_size"] * ((exit_price - float(trade["entry_price"])) / float(trade["entry_price"]))
        close_event = {
            "trade_no": trade["trade_no"],
            "symbol": trade["symbol"],
            "divergence": "demo-exit",
            "entry_time": trade["entry_time"],
            "exit_time": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            "entry_price": trade["entry_price"],
            "exit_price": exit_price,
            "trade_size": trade["trade_size"],
            "ret_pct": (pnl / trade["trade_size"]) * 100 if trade["trade_size"] else 0.0,
            "pnl": pnl,
            "ml_confidence": 0.5,
            "ml_action": "demo_close",
            "status": "demo_closed",
            "reason": "Demo trade auto-closed",
        }
        print(f"[DEMO_TRADE] Closed demo trade {trade['trade_no']} for {trade['symbol']}")
        queue_demo_event(close_event)

    # Use a background thread with sleep to avoid timer GC quirks
    def _worker():
        try:
            time.sleep(max(1, hold_seconds))
            _complete()
        except Exception as exc:
            # Log but do not crash the main app
            try:
                with open("server.err.log", "a", encoding="utf-8") as fh:
                    fh.write(f"[DEMO_TRADE] auto-close failed for {trade.get('trade_no')} {trade.get('symbol')}: {exc}\n")
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


@router.post("/live/demo_trade")
def live_demo_trade(req: DemoTradeRequest):
    def _latest_price(sym: str) -> float:
        try:
            df = fetch_klines(sym, timeframe="3m", limit=1, category="linear", base_url=BYBIT_MAINNET)
            if not df.empty and "close" in df.columns:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        # fallback to a reasonable band if live fetch fails
        return round(random.uniform(90, 110), 2)

    trade_no = random.randint(100000, 999999)
    entry_price = _latest_price(req.symbol)
    trade_size = round(req.equity_pct * 10000, 2)
    entry_time = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    event = {
        "trade_no": trade_no,
        "symbol": req.symbol,
        "divergence": "demo-long",
        "entry_time": entry_time,
        "exit_time": None,
        "entry_price": entry_price,
        "exit_price": entry_price,
        "trade_size": trade_size,
        "ret_pct": 0.0,
        "pnl": 0.0,
        "ml_confidence": 0.99,
        "ml_action": "take",
        "status": "taken",
        "reason": "Demo trade fired",
    }
    print(
        f"[DEMO_TRADE] Fired demo trade {trade_no} on {req.symbol} "
        f"size={trade_size:.2f} USDT hold={req.hold_seconds}s"
    )
    queue_demo_event(event)
    _schedule_demo_close(event, req.hold_seconds)
    return {"ok": True, "event": event}
