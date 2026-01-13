from __future__ import annotations

import threading
import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

try:
    import ccxt
except Exception:
    ccxt = None

from engine.bybit_data import fetch_instruments_all

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz():
    try:
        from engine.storage import DB_PATH as _DB_PATH
    except Exception:
        _DB_PATH = None
    return {"ok": True, "db": _DB_PATH}


@router.post("/restart")
def restart():
    import os

    def _do_restart():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"ok": True, "restarting": True}


@router.get("/symbols")
def symbols() -> Dict[str, List[str]]:
    # Prefer Bybit v5 instruments (full list, no 200 cap)
    try:
        raw = fetch_instruments_all()

        def to_slash(s: str) -> str:
            s = s.upper()
            return s[:-4] + "/USDT" if s.endswith("USDT") else s

        bad_suffix = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
        syms = []
        for sym in raw or []:
            u = sym.upper()
            if any(u.endswith(suf) for suf in bad_suffix):
                continue
            syms.append(to_slash(u))
        if not syms:
            syms = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        return {"symbols": sorted(set(syms))}
    except Exception:
        # CCXT fallback without slicing to 200
        out = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        try:
            if ccxt is not None:
                ex = ccxt.binance()
                mkts = ex.load_markets()
                out = sorted([m for m in mkts if m.endswith("/USDT")])
        except Exception:
            pass
        return {"symbols": out}


@router.get("/")
def root_redirect():
    # Default to the new Lab page
    return RedirectResponse(url="/static/magic_v2.html", status_code=307)


@router.get("/magic")
def magic_redirect():
    return RedirectResponse(url="/static/magic.html", status_code=307)


@router.get("/debug/codehash")
def debug_codehash():
    try:
        import hashlib
        import inspect

        from routers.backtest import backtest

        src = inspect.getsource(backtest)
        h = hashlib.sha1(src.encode("utf-8")).hexdigest()
        return {"backtest_sha1": h, "len": len(src)}
    except Exception as e:
        return {"error": str(e)}
