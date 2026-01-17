import base64
import hashlib
import os
from typing import Optional


def _secret_seed() -> str:
    seed = os.environ.get("MYSTRIX_SECRET_KEY")
    if seed:
        return seed
    fallback = os.environ.get("ADMIN_PASSWORD", "")
    if fallback:
        return fallback
    raise RuntimeError("MYSTRIX_SECRET_KEY is not set")


def _key_bytes() -> bytes:
    seed = _secret_seed().encode("utf-8")
    return hashlib.sha256(seed).digest()


def encrypt_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    raw = value.encode("utf-8")
    key = _key_bytes()
    out = bytes((b ^ key[i % len(key)]) for i, b in enumerate(raw))
    return base64.urlsafe_b64encode(out).decode("utf-8")


def decrypt_secret(token: Optional[str]) -> str:
    if not token:
        return ""
    try:
        data = base64.urlsafe_b64decode(token.encode("utf-8"))
    except Exception:
        return ""
    key = _key_bytes()
    out = bytes((b ^ key[i % len(key)]) for i, b in enumerate(data))
    return out.decode("utf-8", errors="ignore")


def mask_secret(value: Optional[str], show: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= show:
        return "*" * len(value)
    return "*" * (len(value) - show) + value[-show:]
