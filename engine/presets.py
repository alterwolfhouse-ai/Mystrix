from __future__ import annotations

import json
import time
import sqlite3
from typing import Dict

from . import storage as _st


def _norm_symbol(symbol: str) -> str:
    return (symbol or "").upper().replace("/", "")


def _ensure_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS presets (
          product TEXT NOT NULL,
          symbol  TEXT NOT NULL,
          slot    TEXT NOT NULL,
          params  TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY(product, symbol, slot)
        )
        """
    )


def save_preset(product: str, symbol: str, slot: str, params: Dict) -> None:
    sym = _norm_symbol(symbol)
    now = int(time.time() * 1000)
    # Prefer engine.storage connection context if available
    if hasattr(_st, "_conn"):
        with _st._conn() as con:  # type: ignore[attr-defined]
            _ensure_table(con)
            con.execute(
                "INSERT INTO presets(product,symbol,slot,params,updated_at) VALUES (?,?,?,?,?)\n"
                "ON CONFLICT(product,symbol,slot) DO UPDATE SET params=excluded.params, updated_at=excluded.updated_at",
                (product, sym, slot, json.dumps(params), now),
            )
            return
    # Fallback direct connection
    path = getattr(_st, "DB_PATH", "data_cache.db")
    con = sqlite3.connect(str(path))
    try:
        _ensure_table(con)
        con.execute(
            "INSERT INTO presets(product,symbol,slot,params,updated_at) VALUES (?,?,?,?,?)\n"
            "ON CONFLICT(product,symbol,slot) DO UPDATE SET params=excluded.params, updated_at=excluded.updated_at",
            (product, sym, slot, json.dumps(params), now),
        )
        con.commit()
    finally:
        con.close()


def get_presets(product: str, symbol: str) -> Dict[str, Dict]:
    sym = _norm_symbol(symbol)
    out: Dict[str, Dict] = {"bull": {}, "bear": {}, "chop": {}}
    if hasattr(_st, "_conn"):
        with _st._conn() as con:  # type: ignore[attr-defined]
            _ensure_table(con)
            cur = con.execute(
                "SELECT slot, params, updated_at FROM presets WHERE product=? AND symbol=?",
                (product, sym),
            )
            for slot, params, updated_at in cur.fetchall():
                try:
                    out[slot] = {"params": json.loads(params), "updatedAt": int(updated_at)}
                except Exception:
                    continue
            return out
    # Fallback
    path = getattr(_st, "DB_PATH", "data_cache.db")
    con = sqlite3.connect(str(path))
    try:
        _ensure_table(con)
        cur = con.execute(
            "SELECT slot, params, updated_at FROM presets WHERE product=? AND symbol=?",
            (product, sym),
        )
        for slot, params, updated_at in cur.fetchall():
            try:
                out[slot] = {"params": json.loads(params), "updatedAt": int(updated_at)}
            except Exception:
                continue
        return out
    finally:
        con.close()


def delete_preset(product: str, symbol: str, slot: str) -> None:
    sym = _norm_symbol(symbol)
    if hasattr(_st, "_conn"):
        with _st._conn() as con:  # type: ignore[attr-defined]
            _ensure_table(con)
            con.execute("DELETE FROM presets WHERE product=? AND symbol=? AND slot=?", (product, sym, slot))
            return
    # Fallback
    path = getattr(_st, "DB_PATH", "data_cache.db")
    con = sqlite3.connect(str(path))
    try:
        _ensure_table(con)
        con.execute("DELETE FROM presets WHERE product=? AND symbol=? AND slot=?", (product, sym, slot))
        con.commit()
    finally:
        con.close()
