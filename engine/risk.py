from dataclasses import dataclass
import numpy as np

@dataclass
class LtfRisk:
    pred_score: float
    sl_price: float
    div_score: float
    rsi_3m: float

def position_size(equity: float, entry: float, stop: float,
                  base_risk_pct: float, C: float, kelly_frac: float) -> tuple[float,float]:
    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0 or entry<=0: return 0.0, 0.0
    risk_pct = base_risk_pct * (0.5 + 1.5*C)
    rr_approx = 1.8
    edge = C
    kelly = max(0.0, (edge*rr_approx - (1-edge))/rr_approx)
    risk_pct = min(0.05, risk_pct + kelly*kelly_frac)  # cap 5%
    risk_amt = equity * risk_pct
    qty = risk_amt / per_unit_risk
    return float(max(0.0, qty)), float(risk_pct)

