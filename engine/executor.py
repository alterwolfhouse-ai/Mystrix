from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class Position:
    side: str
    qty: float
    entry: float
    stop: float

class Executor3M:
    def __init__(self, rsi_os: int, rsi_ob: int, max_wait_bars: int, cooldown_bars: int):
        self.rsi_os = rsi_os
        self.rsi_ob = rsi_ob
        self.max_wait_bars = max_wait_bars
        self.cooldown_bars = cooldown_bars

        self.await_div_long = False
        self.await_bars_long = 0
        self.await_div_bear = False
        self.await_bars_bear = 0
        self.cooldown = 0
        self.pos: Optional[Position] = None

    def on_bar(self, symbol: str, bar_high: float, bar_low: float, bar_close: float,
               rsi: float, bullCond: bool, bearCond: bool, bias: int, trad: str,
               conf_for_sizing: float, div_score: float, stop_candidate: float,
               equity: float, size_fn, gate_open: bool = True) -> Optional[Dict]:
        # Arm long when RSI <= OS and flat
        if self.pos is None and rsi <= self.rsi_os:
            self.await_div_long, self.await_bars_long = True, 0
        if self.await_div_long:
            self.await_bars_long += 1
            if self.await_bars_long > self.max_wait_bars:
                self.await_div_long, self.await_bars_long = False, 0

        # Arm bear when in pos and RSI >= OB
        if self.pos is not None and rsi >= self.rsi_ob:
            self.await_div_bear, self.await_bars_bear = True, 0
        if self.await_div_bear:
            self.await_bars_bear += 1
            if self.await_bars_bear > self.max_wait_bars:
                self.await_div_bear, self.await_bars_bear = False, 0

        # Entry gate
        entry_raw = (self.pos is None) and self.await_div_long and bullCond
        bias_ok = (bias >= 0) or (trad == "chop" and div_score >= 0.75)
        can_enter = (self.cooldown == 0) and bias_ok and bool(gate_open)

        if entry_raw and can_enter:
            entry = bar_close
            stop  = stop_candidate
            qty, risk_pct = size_fn(equity, entry, stop, conf_for_sizing)
            if qty > 0:
                self.pos = Position(side="long", qty=qty, entry=entry, stop=stop)
                self.await_div_long = False; self.await_bars_long = 0
                return {"type":"enter_long", "symbol":symbol, "entry":entry, "stop":stop, "qty":qty, "risk_pct":risk_pct}

        # Exit on bear divergence after OB arm
        if self.pos is not None and self.await_div_bear and bearCond:
            exit_price = bar_close
            trade = {"type":"exit_normal", "symbol":symbol, "exit":exit_price, "entry":self.pos.entry, "qty":self.pos.qty}
            self.pos = None; self.await_div_bear=False; self.await_bars_bear=0
            return trade

        # Stop loss
        if self.pos is not None and bar_low <= self.pos.stop:
            exit_price = self.pos.stop
            trade = {"type":"exit_sl", "symbol":symbol, "exit":exit_price, "entry":self.pos.entry, "qty":self.pos.qty}
            self.pos = None
            self.cooldown = self.cooldown_bars
            return trade

        # Cooldown tick
        if self.cooldown > 0:
            self.cooldown -= 1

        return None
