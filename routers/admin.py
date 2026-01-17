from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from engine.storage import _conn
from services.auth import get_user_from_sid
from services.secure_store import decrypt_secret, encrypt_secret, mask_secret


router = APIRouter(tags=["admin"])


class DefaultsPayload(BaseModel):
    timeframe_hist: str = Field(default="3m")
    overrides: Dict[str, Any] = Field(default_factory=dict)


class UserAccessPayload(BaseModel):
    user_id: int
    has_mystrix_plus: bool = False
    has_backtest: bool = False
    has_autotrader: bool = False
    has_chat: bool = False
    is_active: bool = True
    plan_expires_at: int | None = None
    plan_name: str = ""
    plan_note: str = ""


class BulkUserAccessPayload(BaseModel):
    user_ids: List[int] = Field(default_factory=list)
    has_mystrix_plus: bool | None = None
    has_backtest: bool | None = None
    has_autotrader: bool | None = None
    has_chat: bool | None = None
    is_active: bool | None = None
    plan_expires_at: int | None = None
    clear_plan_expires: bool = False
    plan_name: str | None = None
    plan_note: str | None = None


class UserApiPayload(BaseModel):
    user_id: int
    api_key: str | None = None
    api_secret: str | None = None
    api_label: str | None = None
    clear: bool = False


def _require_admin(request: Request) -> Dict[str, Any]:
    user = get_user_from_sid(request.cookies.get("sid"))
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin required")
    return user


def _log_admin_action(con, admin_id: int | None, action: str, target_user_id: int | None = None, payload: Dict[str, Any] | None = None) -> None:
    data = payload or {}
    con.execute(
        """
        INSERT INTO admin_audit(admin_id, action, target_user_id, payload, created_at)
        VALUES (?,?,?,?,?)
        """,
        (
            int(admin_id) if admin_id else None,
            action,
            int(target_user_id) if target_user_id else None,
            json.dumps(data, default=str),
            int(time.time()),
        ),
    )


def _ledger_totals(con) -> Tuple[Dict[int, Dict[str, Any]], float]:
    rows = con.execute(
        """
        SELECT user_id,
               COALESCE(SUM(principal_delta),0),
               COALESCE(SUM(profit_delta),0),
               COALESCE(SUM(CASE WHEN principal_delta>0 THEN principal_delta ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN principal_delta<0 THEN -principal_delta ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN profit_delta>0 THEN profit_delta ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN profit_delta<0 THEN -profit_delta ELSE 0 END),0),
               MAX(created_at),
               MAX(CASE WHEN kind='deposit' THEN created_at ELSE NULL END),
               MAX(CASE WHEN kind='withdrawal' THEN created_at ELSE NULL END),
               MAX(CASE WHEN kind='profit_alloc' THEN created_at ELSE NULL END)
        FROM ledger_entries
        GROUP BY user_id
        """
    ).fetchall()
    totals: Dict[int, Dict[str, Any]] = {}
    total_principal = 0.0
    for row in rows:
        user_id = int(row[0])
        principal = float(row[1] or 0.0)
        profit = float(row[2] or 0.0)
        totals[user_id] = {
            "principal_balance": principal,
            "profit_balance": profit,
            "total_deposits": float(row[3] or 0.0),
            "total_withdrawals": float(row[4] or 0.0),
            "total_profit": float(row[5] or 0.0),
            "total_profit_withdrawn": float(row[6] or 0.0),
            "last_ledger_at": row[7],
            "last_deposit_at": row[8],
            "last_withdrawal_at": row[9],
            "last_profit_at": row[10],
        }
        if principal > 0:
            total_principal += principal
    return totals, total_principal


def _user_balances(con, user_id: int) -> Tuple[float, float]:
    row = con.execute(
        """
        SELECT COALESCE(SUM(principal_delta),0), COALESCE(SUM(profit_delta),0)
        FROM ledger_entries WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()
    return float(row[0] or 0.0), float(row[1] or 0.0)


def _validate_amount(amount: float) -> float:
    try:
        val = float(amount)
    except Exception:
        raise HTTPException(status_code=400, detail="amount must be a number")
    if val <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")
    return val


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
        ledger_totals, total_principal = _ledger_totals(con)
        rows = con.execute(
            """
            SELECT id,email,name,is_admin,created_at,
                   has_mystrix_plus,has_backtest,has_autotrader,has_chat,
                   is_active,plan_expires_at,last_login,plan_name,plan_note,
                   api_key_enc,api_secret_enc,api_label,api_updated_at
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()
    users = [
        {
            "id": r[0],
            "email": r[1],
            "name": r[2],
            "is_admin": bool(r[3]),
            "created_at": r[4],
            "has_mystrix_plus": bool(r[5]),
            "has_backtest": bool(r[6]),
            "has_autotrader": bool(r[7]),
            "has_chat": bool(r[8]),
            "is_active": bool(r[9]),
            "plan_expires_at": r[10],
            "last_login": r[11],
            "plan_name": r[12] or "",
            "plan_note": r[13] or "",
            "api_key_masked": mask_secret(decrypt_secret(r[14] or "")),
            "api_secret_masked": mask_secret(decrypt_secret(r[15] or "")),
            "api_label": r[16] or "",
            "api_updated_at": r[17],
            "principal_balance": ledger_totals.get(r[0], {}).get("principal_balance", 0.0),
            "profit_balance": ledger_totals.get(r[0], {}).get("profit_balance", 0.0),
            "net_balance": ledger_totals.get(r[0], {}).get("principal_balance", 0.0)
            + ledger_totals.get(r[0], {}).get("profit_balance", 0.0),
            "total_deposits": ledger_totals.get(r[0], {}).get("total_deposits", 0.0),
            "total_withdrawals": ledger_totals.get(r[0], {}).get("total_withdrawals", 0.0),
            "total_profit": ledger_totals.get(r[0], {}).get("total_profit", 0.0),
            "total_profit_withdrawn": ledger_totals.get(r[0], {}).get("total_profit_withdrawn", 0.0),
            "last_ledger_at": ledger_totals.get(r[0], {}).get("last_ledger_at"),
            "last_deposit_at": ledger_totals.get(r[0], {}).get("last_deposit_at"),
            "last_withdrawal_at": ledger_totals.get(r[0], {}).get("last_withdrawal_at"),
            "last_profit_at": ledger_totals.get(r[0], {}).get("last_profit_at"),
            "principal_ratio": (ledger_totals.get(r[0], {}).get("principal_balance", 0.0) / total_principal)
            if total_principal > 0
            else 0.0,
        }
        for r in rows
    ]
    return {"users": users}


@router.post("/admin/users/update")
def admin_users_update(payload: UserAccessPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    with _conn() as con:
        con.execute(
            """
            UPDATE users
            SET has_mystrix_plus=?,
                has_backtest=?,
                has_autotrader=?,
                has_chat=?,
                is_active=?,
                plan_expires_at=?,
                plan_name=?,
                plan_note=?
            WHERE id=?
            """,
            (
                1 if payload.has_mystrix_plus else 0,
                1 if payload.has_backtest else 0,
                1 if payload.has_autotrader else 0,
                1 if payload.has_chat else 0,
                1 if payload.is_active else 0,
                payload.plan_expires_at,
                payload.plan_name.strip(),
                payload.plan_note.strip(),
                int(payload.user_id),
            ),
        )
        _log_admin_action(
            con,
            admin.get("id"),
            "user_update",
            payload.user_id,
            {
                "has_mystrix_plus": payload.has_mystrix_plus,
                "has_backtest": payload.has_backtest,
                "has_autotrader": payload.has_autotrader,
                "has_chat": payload.has_chat,
                "is_active": payload.is_active,
                "plan_expires_at": payload.plan_expires_at,
                "plan_name": payload.plan_name,
                "plan_note": payload.plan_note,
            },
        )
    return {"ok": True}


@router.post("/admin/users/bulk_update")
def admin_users_bulk_update(payload: BulkUserAccessPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    ids = [int(i) for i in payload.user_ids or [] if int(i) > 0]
    if not ids:
        raise HTTPException(status_code=400, detail="user_ids required")
    fields: List[str] = []
    params: List[Any] = []
    if payload.has_mystrix_plus is not None:
        fields.append("has_mystrix_plus=?")
        params.append(1 if payload.has_mystrix_plus else 0)
    if payload.has_backtest is not None:
        fields.append("has_backtest=?")
        params.append(1 if payload.has_backtest else 0)
    if payload.has_autotrader is not None:
        fields.append("has_autotrader=?")
        params.append(1 if payload.has_autotrader else 0)
    if payload.has_chat is not None:
        fields.append("has_chat=?")
        params.append(1 if payload.has_chat else 0)
    if payload.is_active is not None:
        fields.append("is_active=?")
        params.append(1 if payload.is_active else 0)
    if payload.clear_plan_expires:
        fields.append("plan_expires_at=NULL")
    elif payload.plan_expires_at is not None:
        fields.append("plan_expires_at=?")
        params.append(payload.plan_expires_at)
    if payload.plan_name is not None:
        fields.append("plan_name=?")
        params.append(payload.plan_name.strip())
    if payload.plan_note is not None:
        fields.append("plan_note=?")
        params.append(payload.plan_note.strip())
    if not fields:
        raise HTTPException(status_code=400, detail="no updates provided")
    placeholders = ",".join(["?"] * len(ids))
    with _conn() as con:
        skipped_admin = con.execute(
            f"SELECT COUNT(*) FROM users WHERE id IN ({placeholders}) AND is_admin=1",
            tuple(ids),
        ).fetchone()
        con.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id IN ({placeholders}) AND is_admin=0",
            tuple(params + ids),
        )
        updated = con.execute("SELECT changes()").fetchone()[0]
        _log_admin_action(
            con,
            admin.get("id"),
            "user_bulk_update",
            None,
            {
                "user_ids": ids,
                "fields": fields,
                "updated": int(updated or 0),
                "skipped_admin": int(skipped_admin[0] or 0),
            },
        )
    return {"ok": True, "updated": int(updated or 0), "skipped_admin": int(skipped_admin[0] or 0)}


@router.post("/admin/users/api")
def admin_users_api(payload: UserApiPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    user_id = int(payload.user_id)
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        now = int(time.time())
        if payload.clear:
            con.execute(
                """
                UPDATE users
                SET api_key_enc='',
                    api_secret_enc='',
                    api_label='',
                    api_updated_at=?
                WHERE id=?
                """,
                (now, user_id),
            )
            _log_admin_action(con, admin.get("id"), "user_api_clear", user_id, {})
            return {"ok": True}

        updates = []
        params: List[Any] = []
        if payload.api_key:
            updates.append("api_key_enc=?")
            params.append(encrypt_secret(payload.api_key.strip()))
        if payload.api_secret:
            updates.append("api_secret_enc=?")
            params.append(encrypt_secret(payload.api_secret.strip()))
        if payload.api_label is not None:
            updates.append("api_label=?")
            params.append(payload.api_label.strip())
        if not updates:
            raise HTTPException(status_code=400, detail="no api updates provided")
        updates.append("api_updated_at=?")
        params.append(now)
        params.append(user_id)
        con.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id=?",
            tuple(params),
        )
        _log_admin_action(
            con,
            admin.get("id"),
            "user_api_update",
            user_id,
            {"api_label": payload.api_label or "", "has_key": bool(payload.api_key), "has_secret": bool(payload.api_secret)},
        )
    return {"ok": True}


class ResetPasswordPayload(BaseModel):
    user_id: int
    new_password: str


class DeleteUserPayload(BaseModel):
    user_id: int


@router.post("/admin/users/reset_password")
def admin_reset_password(payload: ResetPasswordPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    if not payload.new_password or len(payload.new_password) < 6:
        raise HTTPException(400, "password too short")
    from services.auth import hash_pw
    h, salt = hash_pw(payload.new_password)
    with _conn() as con:
        con.execute(
            "UPDATE users SET pass_hash=?, pass_salt=? WHERE id=?",
            (h, salt, int(payload.user_id)),
        )
        _log_admin_action(con, admin.get("id"), "user_reset_password", payload.user_id, {})
    return {"ok": True}


@router.post("/admin/users/logout")
def admin_force_logout(user_id: int, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE user_id=?", (int(user_id),))
        _log_admin_action(con, admin.get("id"), "user_force_logout", int(user_id), {})
    return {"ok": True}


@router.post("/admin/users/delete")
def admin_delete_user(payload: DeleteUserPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    target_id = int(payload.user_id)
    if admin.get("id") == target_id:
        raise HTTPException(status_code=400, detail="cannot delete current admin")
    with _conn() as con:
        row = con.execute("SELECT is_admin FROM users WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        if int(row[0] or 0) == 1:
            raise HTTPException(status_code=403, detail="cannot delete admin")
        con.execute("DELETE FROM sessions WHERE user_id=?", (target_id,))
        con.execute("DELETE FROM favorites WHERE user_id=?", (target_id,))
        con.execute("UPDATE suggestions SET user_id=NULL WHERE user_id=?", (target_id,))
        con.execute("DELETE FROM ledger_entries WHERE user_id=?", (target_id,))
        con.execute("DELETE FROM users WHERE id=?", (target_id,))
        _log_admin_action(con, admin.get("id"), "user_delete", target_id, {})
    return {"ok": True}


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
    admin = _require_admin(request)
    with _conn() as con:
        con.execute("UPDATE suggestions SET resolved=1 WHERE id=?", (int(id),))
        _log_admin_action(con, admin.get("id"), "suggestion_resolve", None, {"suggestion_id": int(id)})
    return {"ok": True}


class LedgerAmountPayload(BaseModel):
    user_id: int
    amount: float
    note: str = ""


class ProfitAllocatePayload(BaseModel):
    amount: float
    note: str = ""


@router.get("/admin/ledger/summary")
def admin_ledger_summary(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    with _conn() as con:
        totals = con.execute(
            """
            SELECT
              COALESCE(SUM(principal_delta),0),
              COALESCE(SUM(profit_delta),0),
              COALESCE(SUM(CASE WHEN principal_delta>0 THEN principal_delta ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN principal_delta<0 THEN -principal_delta ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN profit_delta>0 THEN profit_delta ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN profit_delta<0 THEN -profit_delta ELSE 0 END),0)
            FROM ledger_entries
            """
        ).fetchone()
        active_users = con.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT user_id FROM ledger_entries
              GROUP BY user_id
              HAVING SUM(principal_delta) > 0
            )
            """
        ).fetchone()
        last_batch = con.execute(
            """
            SELECT id, amount, total_principal, allocated_to, note, created_at
            FROM pool_yield_batches
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return {
        "total_principal": float(totals[0] or 0.0),
        "total_profit": float(totals[1] or 0.0),
        "total_deposits": float(totals[2] or 0.0),
        "total_withdrawals": float(totals[3] or 0.0),
        "total_profit_allocated": float(totals[4] or 0.0),
        "total_profit_withdrawn": float(totals[5] or 0.0),
        "active_principal_users": int(active_users[0] or 0),
        "last_batch": None
        if not last_batch
        else {
            "id": last_batch[0],
            "amount": float(last_batch[1] or 0.0),
            "total_principal": float(last_batch[2] or 0.0),
            "allocated_to": int(last_batch[3] or 0),
            "note": last_batch[4] or "",
            "created_at": last_batch[5],
        },
    }


@router.get("/admin/ledger/events")
def admin_ledger_events(request: Request, user_id: int | None = None, limit: int = 50) -> Dict[str, Any]:
    _require_admin(request)
    limit = max(1, min(int(limit or 50), 200))
    args: List[Any] = []
    q = """
        SELECT l.id, l.user_id, u.email, u.name, l.kind,
               l.principal_delta, l.profit_delta, l.note,
               l.created_at, l.batch_id, l.created_by
        FROM ledger_entries l
        LEFT JOIN users u ON l.user_id=u.id
    """
    if user_id:
        q += " WHERE l.user_id=?"
        args.append(int(user_id))
    q += " ORDER BY l.created_at DESC, l.id DESC LIMIT ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(q, tuple(args)).fetchall()
    events = [
        {
            "id": r[0],
            "user_id": r[1],
            "email": r[2],
            "name": r[3],
            "kind": r[4],
            "principal_delta": float(r[5] or 0.0),
            "profit_delta": float(r[6] or 0.0),
            "note": r[7] or "",
            "created_at": r[8],
            "batch_id": r[9],
            "created_by": r[10],
        }
        for r in rows
    ]
    return {"events": events}


@router.get("/admin/ledger/export")
def admin_ledger_export(request: Request, user_id: int | None = None, limit: int = 500) -> Response:
    _require_admin(request)
    limit = max(1, min(int(limit or 500), 5000))
    args: List[Any] = []
    q = """
        SELECT l.id, l.user_id, u.email, u.name, l.kind,
               l.principal_delta, l.profit_delta, l.note,
               l.created_at, l.batch_id, l.created_by
        FROM ledger_entries l
        LEFT JOIN users u ON l.user_id=u.id
    """
    if user_id:
        q += " WHERE l.user_id=?"
        args.append(int(user_id))
    q += " ORDER BY l.created_at DESC, l.id DESC LIMIT ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(q, tuple(args)).fetchall()
    buff = StringIO()
    buff.write("id,user_id,email,name,kind,principal_delta,profit_delta,note,created_at,created_at_iso,batch_id,created_by\n")
    for r in rows:
        ts = r[8] or 0
        iso = ""
        if ts:
            iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        line = [
            r[0],
            r[1],
            (r[2] or "").replace(",", " "),
            (r[3] or "").replace(",", " "),
            r[4],
            r[5],
            r[6],
            (r[7] or "").replace(",", " "),
            ts,
            iso,
            r[9] or "",
            r[10] or "",
        ]
        buff.write(",".join(str(v) for v in line) + "\n")
    return Response(content=buff.getvalue(), media_type="text/csv")


@router.get("/admin/audit")
def admin_audit(request: Request, target_user_id: int | None = None, limit: int = 100) -> Dict[str, Any]:
    _require_admin(request)
    limit = max(1, min(int(limit or 100), 500))
    args: List[Any] = []
    q = """
        SELECT a.id, a.action, a.target_user_id, a.payload, a.created_at,
               au.email, au.name, tu.email, tu.name
        FROM admin_audit a
        LEFT JOIN users au ON a.admin_id=au.id
        LEFT JOIN users tu ON a.target_user_id=tu.id
    """
    if target_user_id:
        q += " WHERE a.target_user_id=?"
        args.append(int(target_user_id))
    q += " ORDER BY a.created_at DESC, a.id DESC LIMIT ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(q, tuple(args)).fetchall()
    events = [
        {
            "id": r[0],
            "action": r[1],
            "target_user_id": r[2],
            "payload": r[3] or "",
            "created_at": r[4],
            "admin_email": r[5],
            "admin_name": r[6],
            "user_email": r[7],
            "user_name": r[8],
        }
        for r in rows
    ]
    return {"events": events}


@router.get("/admin/audit/export")
def admin_audit_export(request: Request, target_user_id: int | None = None, limit: int = 500) -> Response:
    _require_admin(request)
    limit = max(1, min(int(limit or 500), 5000))
    args: List[Any] = []
    q = """
        SELECT a.id, a.action, a.target_user_id, a.payload, a.created_at,
               au.email, au.name, tu.email, tu.name
        FROM admin_audit a
        LEFT JOIN users au ON a.admin_id=au.id
        LEFT JOIN users tu ON a.target_user_id=tu.id
    """
    if target_user_id:
        q += " WHERE a.target_user_id=?"
        args.append(int(target_user_id))
    q += " ORDER BY a.created_at DESC, a.id DESC LIMIT ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(q, tuple(args)).fetchall()
    buff = StringIO()
    buff.write("id,action,target_user_id,admin_email,admin_name,user_email,user_name,payload,created_at,created_at_iso\n")
    for r in rows:
        ts = r[4] or 0
        iso = ""
        if ts:
            iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        line = [
            r[0],
            r[1],
            r[2] or "",
            (r[5] or "").replace(",", " "),
            (r[6] or "").replace(",", " "),
            (r[7] or "").replace(",", " "),
            (r[8] or "").replace(",", " "),
            (r[3] or "").replace(",", " "),
            ts,
            iso,
        ]
        buff.write(",".join(str(v) for v in line) + "\n")
    return Response(content=buff.getvalue(), media_type="text/csv")


@router.post("/admin/ledger/deposit")
def admin_ledger_deposit(payload: LedgerAmountPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    amount = _validate_amount(payload.amount)
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", (int(payload.user_id),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        con.execute(
            """
            INSERT INTO ledger_entries(user_id, principal_delta, profit_delta, kind, note, created_at, created_by)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                int(payload.user_id),
                amount,
                0.0,
                "deposit",
                (payload.note or "").strip(),
                int(time.time()),
                admin.get("id"),
            ),
        )
        _log_admin_action(
            con,
            admin.get("id"),
            "ledger_deposit",
            int(payload.user_id),
            {"amount": amount, "note": (payload.note or "").strip()},
        )
    return {"ok": True}


@router.post("/admin/ledger/withdraw")
def admin_ledger_withdraw(payload: LedgerAmountPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    amount = _validate_amount(payload.amount)
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", (int(payload.user_id),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        principal, _profit = _user_balances(con, int(payload.user_id))
        if principal < amount:
            raise HTTPException(status_code=400, detail="insufficient principal balance")
        con.execute(
            """
            INSERT INTO ledger_entries(user_id, principal_delta, profit_delta, kind, note, created_at, created_by)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                int(payload.user_id),
                -amount,
                0.0,
                "withdrawal",
                (payload.note or "").strip(),
                int(time.time()),
                admin.get("id"),
            ),
        )
        _log_admin_action(
            con,
            admin.get("id"),
            "ledger_withdraw_principal",
            int(payload.user_id),
            {"amount": amount, "note": (payload.note or "").strip()},
        )
    return {"ok": True}


@router.post("/admin/ledger/profit_withdraw")
def admin_ledger_profit_withdraw(payload: LedgerAmountPayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    amount = _validate_amount(payload.amount)
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE id=?", (int(payload.user_id),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        _principal, profit = _user_balances(con, int(payload.user_id))
        if profit < amount:
            raise HTTPException(status_code=400, detail="insufficient profit balance")
        con.execute(
            """
            INSERT INTO ledger_entries(user_id, principal_delta, profit_delta, kind, note, created_at, created_by)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                int(payload.user_id),
                0.0,
                -amount,
                "profit_withdraw",
                (payload.note or "").strip(),
                int(time.time()),
                admin.get("id"),
            ),
        )
        _log_admin_action(
            con,
            admin.get("id"),
            "ledger_withdraw_profit",
            int(payload.user_id),
            {"amount": amount, "note": (payload.note or "").strip()},
        )
    return {"ok": True}


@router.post("/admin/ledger/profit_allocate")
def admin_ledger_profit_allocate(payload: ProfitAllocatePayload, request: Request) -> Dict[str, Any]:
    admin = _require_admin(request)
    amount = _validate_amount(payload.amount)
    note = (payload.note or "").strip()
    now = int(time.time())
    with _conn() as con:
        rows = con.execute(
            """
            SELECT user_id, SUM(principal_delta) AS principal
            FROM ledger_entries
            GROUP BY user_id
            HAVING principal > 0
            """
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=400, detail="no principal balances to allocate")
        total_principal = sum(float(r[1]) for r in rows)
        if total_principal <= 0:
            raise HTTPException(status_code=400, detail="total principal is zero")
        cur = con.execute(
            """
            INSERT INTO pool_yield_batches(amount,total_principal,allocated_to,note,created_at,created_by)
            VALUES (?,?,?,?,?,?)
            """,
            (amount, total_principal, len(rows), note, now, admin.get("id")),
        )
        batch_id = cur.lastrowid
        ordered = sorted(rows, key=lambda r: float(r[1]), reverse=True)
        shares: List[Tuple[int, float]] = []
        allocated = 0.0
        for uid, principal in ordered:
            share = amount * float(principal) / total_principal
            share = round(share, 6)
            shares.append((int(uid), share))
            allocated += share
        remainder = round(amount - allocated, 6)
        if shares and abs(remainder) > 0:
            uid, share = shares[0]
            shares[0] = (uid, round(share + remainder, 6))
        for uid, share in shares:
            if abs(share) < 1e-9:
                continue
            con.execute(
                """
                INSERT INTO ledger_entries(user_id, principal_delta, profit_delta, kind, note, created_at, batch_id, created_by)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (uid, 0.0, float(share), "profit_alloc", note, now, int(batch_id), admin.get("id")),
            )
        _log_admin_action(
            con,
            admin.get("id"),
            "ledger_profit_allocate",
            None,
            {
                "amount": float(amount),
                "note": note,
                "batch_id": int(batch_id),
                "allocated_to": len(rows),
                "total_principal": float(total_principal),
            },
        )
    return {
        "ok": True,
        "batch_id": int(batch_id),
        "total_principal": float(total_principal),
        "allocated_to": len(rows),
        "amount": float(amount),
    }
