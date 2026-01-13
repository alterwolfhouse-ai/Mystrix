from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Dict, Optional

from engine.storage import _conn


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
                "SELECT u.id,u.email,u.name,u.is_admin,s.expires_at FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.sid=?",
                (sid,),
            ).fetchone()
        except Exception:
            # Backward-compat schema: token column
            try:
                row = con.execute(
                    "SELECT u.id,u.email,u.name,u.is_admin,s.expires_at FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=?",
                    (sid,),
                ).fetchone()
            except Exception:
                row = None
        if not row:
            return None
        if int(row[4]) < int(time.time()):
            # Try delete with either column name
            try:
                con.execute("DELETE FROM sessions WHERE sid=?", (sid,))
            except Exception:
                try:
                    con.execute("DELETE FROM sessions WHERE token=?", (sid,))
                except Exception:
                    pass
            return None
        return {"id": row[0], "email": row[1], "name": row[2], "is_admin": bool(row[3])}
