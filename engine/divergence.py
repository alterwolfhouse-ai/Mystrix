import numpy as np
import pandas as pd

def pivot_low(series: pd.Series, left: int, right: int) -> pd.Series:
    win = left + right + 1
    rolled = series.rolling(win, center=True)
    is_min = series.eq(rolled.min())
    # Use nullable boolean during fill to avoid FutureWarning
    return is_min.shift(-right).astype('boolean').fillna(False).astype(bool)

def pivot_high(series: pd.Series, left: int, right: int) -> pd.Series:
    win = left + right + 1
    rolled = series.rolling(win, center=True)
    is_max = series.eq(rolled.max())
    return is_max.shift(-right).astype('boolean').fillna(False).astype(bool)

def valuewhen(cond: pd.Series, values: pd.Series, occurrence:int) -> pd.Series:
    idx = cond.replace(False, np.nan).cumsum()
    out = values.where(cond).groupby(idx).transform("last").shift(occurrence)
    return out.ffill()

def bull_divergence(rsi: pd.Series, low: pd.Series,
                    left: int, right: int,
                    range_low: int, range_up: int) -> pd.Series:
    rsiR = rsi.shift(right)
    pl = pivot_low(rsi, left, right)
    prev_rsiR = valuewhen(pl, rsiR, 1)
    lowR = low.shift(right)
    prev_lowR = valuewhen(pl, lowR, 1)
    rsiHL = rsiR > prev_rsiR
    priceLL = lowR < prev_lowR
    prev_pl = pl.shift(1).astype('boolean').fillna(False).astype(bool)
    bars_since_prev = (~prev_pl).astype(int).groupby(prev_pl.cumsum().fillna(0)).cumsum()
    in_range = bars_since_prev.between(range_low, range_up)
    return (pl & rsiHL & priceLL & in_range).fillna(False)

def bear_divergence(rsi: pd.Series, high: pd.Series,
                    left: int, right: int,
                    range_low: int, range_up: int) -> pd.Series:
    rsiR = rsi.shift(right)
    ph = pivot_high(rsi, left, right)
    prev_rsiR = valuewhen(ph, rsiR, 1)
    highR = high.shift(right)
    prev_highR = valuewhen(ph, highR, 1)
    rsiLH = rsiR < prev_rsiR
    priceHH = highR > prev_highR
    prev_ph = ph.shift(1).astype('boolean').fillna(False).astype(bool)
    bars_since_prev = (~prev_ph).astype(int).groupby(prev_ph.cumsum().fillna(0)).cumsum()
    in_range = bars_since_prev.between(range_low, range_up)
    return (ph & rsiLH & priceHH & in_range).fillna(False)
