import numpy as np
import pandas as pd

def rsi_wilder(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/length, adjust=False).mean()
    roll_down = down.ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def ema(series: pd.Series, length:int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def atr(df: pd.DataFrame, length=14) -> pd.Series:
    c = df["close"]
    tr = np.maximum(df["high"] - df["low"],
          np.maximum((df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs()))
    return pd.Series(tr, index=df.index).ewm(alpha=1/length, adjust=False).mean()

def chop_index(df: pd.DataFrame, length=14) -> pd.Series:
    c = df["close"]
    tr_sum = np.maximum(df["high"] - df["low"],
              np.maximum((df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs())
             ).rolling(length).sum()
    hh = df["high"].rolling(length).max()
    ll = df["low"].rolling(length).min()
    denom = (hh - ll).replace(0, np.nan)
    return 100 * np.log10(tr_sum / denom) / np.log10(length)

def bollinger(close: pd.Series, period=20, dev=2.0):
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = ma + dev*sd
    lower = ma - dev*sd
    return upper, ma, lower

