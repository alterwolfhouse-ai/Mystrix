from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engine.storage import _conn
from services.auth import get_user_from_sid


router = APIRouter(tags=["admin"])


class DefaultsPayload(BaseModel):
    timeframe_hist: str = Field(default="3m")
    overrides: Dict[str, Any] = Field(default_factory=dict)


def _require_admin(request: Request) -> Dict[str, Any]:
    user = get_user_from_sid(request.cookies.get("sid"))
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin required")
    return user


def _load_defaults() -> Dict[str, Any]:
    default_payload = {"timeframe_hist": "3m", "overrides": {}}
    with _conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", ("engine_defaults",)).fetchone()
    if not row or not row[0]:
        return default_payload
    try:
        data = json.loads(row[0])
        if not isinstance(data, dict):
            return default_payload
        data.setdefault("timeframe_hist", "3m")
        data.setdefault("overrides", {})
        return data
    except Exception:
        return default_payload


@router.get("/defaults")
def defaults_get() -> Dict[str, Any]:
    return _load_defaults()


@router.post("/admin/defaults")
def defaults_set(req: DefaultsPayload, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    payload = {"timeframe_hist": req.timeframe_hist or "3m", "overrides": req.overrides or {}}
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES (?,?,?)",
            ("engine_defaults", json.dumps(payload), int(time.time())),
        )
    return {"ok": True}


@router.get("/admin/users")
def admin_users(request: Request) -> Dict[str, List[Dict[str, Any]]]:
    _require_admin(request)
    with _conn() as con:
        rows = con.execute(
            "SELECT id,email,name,is_admin,created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    users = [
        {"id": r[0], "email": r[1], "name": r[2], "is_admin": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]
    return {"users": users}


@router.get("/admin/suggestions")
def admin_suggestions(request: Request) -> Dict[str, List[Dict[str, Any]]]:
    _require_admin(request)
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.id, u.email, s.text, s.created_at, s.resolved
            FROM suggestions s
            LEFT JOIN users u ON s.user_id=u.id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
    suggestions = [
        {
            "id": r[0],
            "email": r[1],
            "text": r[2],
            "created_at": r[3],
            "resolved": bool(r[4]),
        }
        for r in rows
    ]
    return {"suggestions": suggestions}


@router.post("/admin/suggestions/resolve")
def admin_suggestions_resolve(id: int, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    with _conn() as con:
        con.execute("UPDATE suggestions SET resolved=1 WHERE id=?", (int(id),))
    return {"ok": True}
