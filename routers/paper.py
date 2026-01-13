from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Body

from schemas.paper import PaperCloseRequest, PaperInitRequest, PaperOrderRequest
from services.paper_state import close_order, open_order, reset, snapshot, tick


router = APIRouter(tags=["paper"])


@router.post("/paper/init")
def paper_init(req: PaperInitRequest):
    balance = reset(req.balance)
    return {"ok": True, "balance": balance}


@router.get("/paper/balance")
def paper_balance():
    return snapshot()


@router.post("/paper/order")
def paper_order(req: PaperOrderRequest):
    trade = open_order(req.symbol, req.side, req.size)
    return {"ok": True, "trade": trade}


@router.post("/paper/close")
def paper_close(req: PaperCloseRequest):
    try:
        trade = close_order(req.trade_id)
        return {"ok": True, "trade": trade}
    except KeyError:
        raise HTTPException(status_code=404, detail="trade not found")


@router.post("/paper/tick")
def paper_tick(payload: Any = Body(None)):
    symbols: Optional[list[str]] = None
    if isinstance(payload, list):
        symbols = payload
    elif isinstance(payload, dict) and "symbols" in payload:
        val = payload.get("symbols")
        if isinstance(val, list):
            symbols = val
    result = tick(symbols)
    return result
