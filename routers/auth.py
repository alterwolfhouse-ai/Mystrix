from __future__ import annotations

import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request, Response

from engine.storage import _conn
from schemas.auth import FavReq, LoginReq, SignupReq, SuggestReq
from services.auth import create_session, get_user_from_sid, hash_pw


router = APIRouter(tags=["auth"])


@router.post("/auth/signup")
def auth_signup(req: SignupReq):
    try:
        h, salt = hash_pw(req.password)
        now = int(time.time())
        with _conn() as con:
            con.execute(
                "INSERT INTO users(email,name,pass_hash,pass_salt,created_at) VALUES (?,?,?,?,?)",
                (req.email.strip(), (req.name or "").strip(), h, salt, now),
            )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/auth/login")
def auth_login(req: LoginReq, response: Response):
    try:
        login_key = req.email.strip()
        with _conn() as con:
            row = con.execute(
                "SELECT id, pass_hash, pass_salt FROM users WHERE email=?",
                (login_key,),
            ).fetchone()
            if not row:
                # Fallback: allow login by name (case-insensitive)
                row = con.execute(
                    "SELECT id, pass_hash, pass_salt FROM users WHERE LOWER(name)=LOWER(?)",
                    (login_key,),
                ).fetchone()
        if not row:
            raise HTTPException(401, "invalid credentials")
        uid = int(row[0])
        phash = row[1] if row[1] is not None else ""
        salt_hex = row[2]
        use_salt = salt_hex if (isinstance(salt_hex, str) and len(salt_hex) % 2 == 0) else None
        calc, _ = hash_pw(req.password, use_salt)
        if calc != str(phash):
            raise HTTPException(401, "invalid credentials")
        sid = create_session(uid)
        response.set_cookie("sid", sid, httponly=True, samesite="lax", max_age=7 * 24 * 3600, path="/")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        # Dev-friendly error; avoid 500 loops during setup
        raise HTTPException(401, f"login failed: {type(e).__name__}")


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    sid = request.cookies.get("sid")
    if sid:
        with _conn() as con:
            con.execute("DELETE FROM sessions WHERE sid=?", (sid,))
    response.delete_cookie("sid", path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = get_user_from_sid(request.cookies.get("sid"))
    return {"user": user}


@router.get("/favorites")
def favorites_get(request: Request):
    user = get_user_from_sid(request.cookies.get("sid"))
    if not user:
        return {"favorites": []}
    with _conn() as con:
        rows = con.execute(
            "SELECT symbol FROM favorites WHERE user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return {"favorites": [r[0] for r in rows]}


@router.post("/favorites")
def favorites_post(req: FavReq, request: Request):
    user = get_user_from_sid(request.cookies.get("sid"))
    if not user:
        raise HTTPException(401, "login required")
    sym = req.symbol.strip().upper()
    now = int(time.time())
    with _conn() as con:
        exists = con.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND symbol=?",
            (user["id"], sym),
        ).fetchone()
        if exists:
            con.execute("DELETE FROM favorites WHERE user_id=? AND symbol=?", (user["id"], sym))
        else:
            con.execute(
                "INSERT OR IGNORE INTO favorites(user_id,symbol,created_at) VALUES (?,?,?)",
                (user["id"], sym, now),
            )
    return {"ok": True}


@router.post("/suggest_coin")
def suggest_coin(req: SuggestReq, request: Request):
    user = get_user_from_sid(request.cookies.get("sid"))
    uid = user["id"] if user else None
    now = int(time.time())
    with _conn() as con:
        con.execute(
            "INSERT INTO suggestions(user_id,text,created_at) VALUES (?,?,?)",
            (uid, req.text.strip(), now),
        )
    return {"ok": True}
