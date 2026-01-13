import os
import joblib
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None  # if missing, returns neutral 0.5

@dataclass
class MLConfig:
    lookahead_bars: int = 20
    train_min_rows: int = 3000
    retrain_every_bars: int = 800
    model_path: str = ".ml_entry_conf.pkl"

class MLAssist:
    def __init__(self, cfg: MLConfig = MLConfig()):
        self.cfg = cfg
        self.model: Optional[LGBMClassifier] = None
        self.last_train_idx: int = -1
        if os.path.exists(self.cfg.model_path):
            try:
                self.model = joblib.load(self.cfg.model_path)
            except Exception:
                self.model = None

    def maybe_retrain(self, df3m: pd.DataFrame):
        if LGBMClassifier is None: return
        if len(df3m) < self.cfg.train_min_rows: return
        if self.last_train_idx != -1 and (len(df3m)-self.last_train_idx) < self.cfg.retrain_every_bars:
            return
        df = df3m.reset_index(drop=True)
        close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
        y = []
        for i in range(len(df) - self.cfg.lookahead_bars - 1):
            entry = close.iloc[i]
            future = close.iloc[i+1 : i + self.cfg.lookahead_bars + 1]
            r = (future.max() - entry) / (0.01 * entry)
            y.append(int(r > 0.0))
        y = pd.Series(y, dtype=int)
        if y.empty: return
        mom14 = close.pct_change().rolling(14).mean()
        volz  = (vol - vol.rolling(50).mean()) / (vol.rolling(50).std().replace(0, np.nan))
        atrp  = (high - low).rolling(14).mean() / close
        X = pd.DataFrame({"mom14": mom14, "volz": volz.clip(-5,5), "atrp": atrp}).fillna(0.0).iloc[:len(y)]
        model = LGBMClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0)
        model.fit(X, y)
        self.model = model
        self.last_train_idx = len(df3m)
        try: joblib.dump(self.model, self.cfg.model_path)
        except Exception: pass

    def entry_confidence(self, df3m: pd.DataFrame, htf_bias: int, htf_conf: float, mid_flag: str, mid_conf: float) -> float:
        if self.model is None or LGBMClassifier is None: return 0.5
        df = df3m.copy()
        close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
        mom14 = close.pct_change().rolling(14).mean().iloc[-1]
        volz  = ((vol - vol.rolling(50).mean()) / (vol.rolling(50).std().replace(0, np.nan))).iloc[-1]
        atrp  = ((high - low).rolling(14).mean() / close).iloc[-1]
        mid_code = {"trend": 1.0, "mixed": 0.0, "chop": -1.0}.get(mid_flag, 0.0)
        X = pd.DataFrame([{
            "mom14": float(0.0 if np.isnan(mom14) else mom14),
            "volz":  float(0.0 if np.isnan(volz)  else max(-5, min(5, volz))),
            "atrp":  float(0.0 if np.isnan(atrp)  else atrp),
            "htf_bias": float(htf_bias),
            "htf_conf": float(htf_conf),
            "mid_code": float(mid_code),
            "mid_conf": float(mid_conf),
        }])
        try:
            proba = self.model.predict_proba(X)[0, 1]
            return float(max(0.0, min(1.0, proba)))
        except Exception:
            return 0.5

