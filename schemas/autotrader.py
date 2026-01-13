from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AutoTraderBalanceRequest(BaseModel):
    base_url: str = "https://api.bybit.com"
    api_key: str
    api_secret: str
    exchange: str = "bybit"
    account_type: str = "contract"
    margin_mode: Optional[str] = None
    environment: Optional[str] = None  # live | testnet


class AutoTraderOrderRequest(BaseModel):
    base_url: str = "https://api.bybit.com"
    api_key: str
    api_secret: str
    exchange: str = "bybit"
    account_type: str = "contract"
    margin_mode: Optional[str] = None
    environment: Optional[str] = None  # live | testnet
    symbol: str
    side: str
    order_type: str = "Market"
    qty: Optional[float] = None
    notional_usdt: Optional[float] = None
    reduce_only: bool = False
    position_idx: Optional[int] = None
    confirm: bool = False


class AutoTraderDemoRequest(AutoTraderOrderRequest):
    symbol: str = "BNB/USDT"
    side: str = "buy"
    notional_usdt: float = 500.0
    hold_seconds: int = 45


class AutoTraderTradingStopRequest(BaseModel):
    base_url: str = "https://api.bybit.com"
    api_key: str
    api_secret: str
    exchange: str = "bybit"
    account_type: str = "contract"
    margin_mode: Optional[str] = None
    environment: Optional[str] = None  # live | testnet
    symbol: str
    side: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_idx: Optional[int] = None
    confirm: bool = False
