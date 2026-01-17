from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Dict, Optional

from engine.storage import _conn

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Fantum1183").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Fantum@36")


def is_reserved_admin_identity(value: str) -> bool:
    if not value:
        return False
    return value.strip().lower() == ADMIN_USERNAME.lower()


def ensure_admin_user() -> None:
    username = ADMIN_USERNAME.strip()
    if not username:
        return
    h, salt = hash_pw(ADMIN_PASSWORD)
    now = int(time.time())
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE email=?", (username,)).fetchone()
        if row:
            con.execute(
                """
                UPDATE users
                SET pass_hash=?,
                    pass_salt=?,
                    is_admin=1,
                    has_mystrix_plus=1,
                    has_backtest=1,
                    has_autotrader=1,
                    has_chat=1,
                    is_active=1
                WHERE email=?
                """,
                (h, salt, username),
            )
        else:
            con.execute(
                """
                INSERT INTO users(
                  email,name,pass_hash,pass_salt,is_admin,created_at,
                  has_mystrix_plus,has_backtest,has_autotrader,has_chat,
                  is_active,plan_expires_at,last_login,plan_name,plan_note
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    username,
                    "Admin",
                    h,
                    salt,
                    1,
                    now,
                    1,
                    1,
                    1,
                    1,
                    1,
                    None,
                    int(time.time()),
                    "Admin",
                    "System owner",
                ),
            )


def hash_pw(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Hash password with pbkdf2_hmac and return digest + salt."""
    if salt_hex is None:
        salt = os.urandom(16)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return dk.hex(), salt_hex


def create_session(user_id: int) -> str:
    """Create or replace a session token for the given user."""
    sid = secrets.token_hex(24)
    now = int(time.time())
    exp = now + 7 * 24 * 3600
    with _conn() as con:
        try:
            con.execute(
                "INSERT OR REPLACE INTO sessions(sid,user_id,created_at,expires_at) VALUES (?,?,?,?)",
                (sid, user_id, now, exp),
            )
        except Exception:
            # Backward-compat: older schema uses token + no created_at
            con.execute(
                "INSERT OR REPLACE INTO sessions(token,user_id,expires_at) VALUES (?,?,?)",
                (sid, user_id, exp),
            )
    return sid


def get_user_from_sid(sid: str | None) -> Optional[Dict]:
    """Resolve user details from a session id cookie; handles older token schema."""
    if not sid:
        return None
    with _conn() as con:
        row = None
        try:
            row = con.execute(
                """
                SELECT u.id,u.email,u.name,u.is_admin,u.has_mystrix_plus,u.has_backtest,u.has_autotrader,u.has_chat,
                       u.is_active,u.plan_expires_at,u.last_login,u.plan_name,u.plan_note,s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id=u.id
                WHERE s.sid=?
                """,
                (sid,),
            ).fetchone()
        except Exception:
            # Backward-compat schema: token column
            try:
                row = con.execute(
                    """
                    SELECT u.id,u.email,u.name,u.is_admin,u.has_mystrix_plus,u.has_backtest,u.has_autotrader,u.has_chat,
                           u.is_active,u.plan_expires_at,u.last_login,u.plan_name,u.plan_note,s.expires_at
                    FROM sessions s
                    JOIN users u ON s.user_id=u.id
                    WHERE s.token=?
                    """,
                    (sid,),
                ).fetchone()
            except Exception:
                row = None
        if not row:
            return None
        if int(row[-1]) < int(time.time()):
            # Try delete with either column name
            try:
                con.execute("DELETE FROM sessions WHERE sid=?", (sid,))
            except Exception:
                try:
                    con.execute("DELETE FROM sessions WHERE token=?", (sid,))
                except Exception:
                    pass
            return None
        return {
            "id": row[0],
            "email": row[1],
            "name": row[2],
            "is_admin": bool(row[3]),
            "has_mystrix_plus": bool(row[4]),
            "has_backtest": bool(row[5]),
            "has_autotrader": bool(row[6]),
            "has_chat": bool(row[7]),
            "is_active": bool(row[8]),
            "plan_expires_at": row[9],
            "last_login": row[10],
            "plan_name": row[11] or "",
            "plan_note": row[12] or "",
        }
