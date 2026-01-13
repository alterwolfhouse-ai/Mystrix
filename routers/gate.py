from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Query

from engine.gate import GateConfig, GateScanner
from routers.meta import symbols as list_symbols


router = APIRouter(tags=["gate"])


def _parse_symbols(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


@router.get("/gate/compute")
def gate_compute(
    symbols: Optional[str] = Query(default=None),
    base_tf: str = Query(default="1h"),
    vroc_span: int = Query(default=8),
) -> Dict:
    cfg = GateConfig(base_tf=base_tf, vroc_span=vroc_span)
    scanner = GateScanner(cfg)
    syms = _parse_symbols(symbols)
    if not syms:
        syms = list_symbols().get("symbols", [])
    rows = scanner.scan(syms, base_tf=cfg.base_tf)
    ts = max((r.get("ts", 0) for r in rows), default=0)
    return {"symbols": rows, "ts": ts}


@router.get("/gate/snapshot")
def gate_snapshot() -> Dict:
    scanner = GateScanner()
    return scanner.snapshot()
