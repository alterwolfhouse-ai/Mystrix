from __future__ import annotations

def norm_symbol(sym: str) -> str:
    """Normalize trading symbols into CCXT slash format."""
    s = sym.strip().upper()
    if "/" in s:
        return s
    if s.endswith("USDT"):
        return s[:-4] + "/USDT"
    if s.endswith("USD"):
        return s[:-3] + "/USDT"
    return s
