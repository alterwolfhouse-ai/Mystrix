import pandas as pd
from .indicators import chop_index, ema, bollinger
from .data import resample_ohlcv

try:
    import yfinance as yf
except Exception:
    yf = None

def dxy_ok(threshold: float = 0.02, enabled: bool = True) -> bool:
    if not enabled or yf is None:
        return True
    try:
        dxy = yf.download("DX-Y.NYB", period="2wk", progress=False)["Close"]
        if len(dxy) < 2: return True
        wow = (dxy.iloc[-1] - dxy.iloc[-2]) / dxy.iloc[-2]
        return abs(wow) < threshold
    except Exception:
        return True

def htf_bias(df: pd.DataFrame, ema_short: int, ema_long: int) -> tuple[int, float]:
    d1 = resample_ohlcv(df, "1d")
    w1 = resample_ohlcv(df, "1w")
    if len(d1) < ema_long or len(w1) < 60: return 0, 0.4
    eS = ema(d1["close"], ema_short); eL = ema(d1["close"], ema_long)
    v1 = 1 if eS.iloc[-1] > eL.iloc[-1] else -1
    eW = ema(w1["close"], 50); v2 = 1 if eW.iloc[-1] > eW.iloc[-2] else -1
    votes = v1 + v2
    bias = 1 if votes>=2 else (-1 if votes<=-2 else 0)
    slope = float((eL.iloc[-1]-eL.iloc[-5]) / (eL.iloc[-5] if eL.iloc[-5]!=0 else 1))
    conf = max(0.0, min(1.0, 0.55 + min(0.45, abs(slope)*10)))
    return bias, conf

def mid_chop(df: pd.DataFrame, chop_len: int) -> tuple[str, float]:
    h4 = resample_ohlcv(df, "4h"); h1 = resample_ohlcv(df, "1h")
    if len(h4)<chop_len*3 or len(h1)<chop_len*3: return "mixed", 0.5
    ch = (chop_index(h4, chop_len).iloc[-1] + chop_index(h1, chop_len).iloc[-1]) / 2
    flag = "chop" if ch>61.8 else ("trend" if ch<38.2 else "mixed")
    conf = 1 - min(1.0, abs(ch - (61.8 if flag=="chop" else 38.2))/22.0)
    return flag, float(max(0.0, min(1.0, conf)))

def bb_squeeze(df_1h: pd.DataFrame, bb_period: int, bb_std: float) -> bool:
    up, mid, lo = bollinger(df_1h["close"], bb_period, bb_std)
    width = (up - lo) / mid
    val = width.iloc[-1]
    return bool(pd.notna(val) and val < 0.05)

