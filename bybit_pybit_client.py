"""
Bybit V5 Unified Trading — pure pybit version

Features
--------
- Use Bybit Demo, Testnet, or Mainnet (switch with ENV = "demo" / "testnet" / "mainnet")
- Poll wallet balance every 3 seconds (GET /v5/account/wallet-balance)
- Open a market order (POST /v5/order/create)
- Close position with reduce-only opposite-side market order
- Fetch open orders (GET /v5/order/realtime)
- Fetch current position for a symbol (GET /v5/position/list)
- Fetch trade history (GET /v5/execution/list)
- WebSocket:
    - private order stream  (topic: order)
    - private execution stream (topic: execution)

Docs:
- https://bybit-exchange.github.io/docs/v5/intro
- https://bybit-exchange.github.io/docs/v5/demo
- https://bybit-exchange.github.io/docs/v5/websocket/private/order
- https://bybit-exchange.github.io/docs/v5/websocket/private/execution
"""

import logging
import threading
import time
from typing import Dict, Optional, Any

from pybit.unified_trading import HTTP, WebSocket  # type: ignore

# -----------------------------------------------------------------------------#
# CONFIG — set your keys and environment here
# -----------------------------------------------------------------------------#

API_KEY = "fvn1Vlxl16koNbemzo"
API_SECRET = "EuwCGFxkSpczdrwsrzgrhYNWpYoGBudgrRRH"

# Choose: "demo" (api-demo.bybit.com), "testnet" (api-testnet.bybit.com), or "mainnet"
ENV = "demo"

# Trading defaults
SYMBOL = "BTCUSDT"
CATEGORY = "linear"         # "linear" (USDT/USDC perps), "inverse", "spot", "option"
ACCOUNT_TYPE = "UNIFIED"    # UTA: UNIFIED (default). For legacy, use CONTRACT/SPOT.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BybitPybitClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol: str,
        category: str = "linear",
        account_type: str = "UNIFIED",
        env: str = "demo",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.category = category
        self.account_type = account_type
        self.env = env.lower()

        self.is_demo = self.env == "demo"
        self.is_testnet = self.env == "testnet"

        logging.info("Initialising Bybit client — env=%s (demo=%s, testnet=%s)", self.env, self.is_demo, self.is_testnet)

        # REST
        self.http = HTTP(
            api_key=self.api_key,
            api_secret=self.api_secret,
            demo=self.is_demo,
            testnet=self.is_testnet,
        )

        # Private WebSocket
        self.ws = WebSocket(
            api_key=self.api_key,
            api_secret=self.api_secret,
            demo=self.is_demo,
            testnet=self.is_testnet,
            channel_type="private",
        )

        self._stop_flag = False
        self.latest_balance: Optional[Dict[str, Any]] = None
        self.latest_positions: Optional[Dict[str, Any]] = None
        self.latest_open_orders: Optional[Dict[str, Any]] = None
        self.latest_trades: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ WS
    def start_private_streams(self) -> None:
        def handle_order(msg: Dict[str, Any]) -> None:
            logging.info("[WS ORDER] %s", msg)

        def handle_execution(msg: Dict[str, Any]) -> None:
            logging.info("[WS EXECUTION] %s", msg)

        self.ws.order_stream(callback=handle_order)
        self.ws.execution_stream(callback=handle_execution)
        logging.info("Started private WebSocket streams (order + execution).")

    # ------------------------------------------------------------- Balance
    def start_balance_poller(self, coin: str = "USDT", interval_sec: int = 3) -> None:
        def loop():
            while not self._stop_flag:
                try:
                    resp = self.http.get_wallet_balance(accountType=self.account_type, coin=coin)
                    self.latest_balance = resp
                    try:
                        total_eq = resp["result"]["list"][0]["totalEquity"]
                        logging.info("[BALANCE] %s totalEquity=%s", coin, total_eq)
                    except Exception:
                        logging.info("[BALANCE RAW] %s", resp)
                except Exception as exc:
                    logging.exception("Balance poll error: %s", exc)
                time.sleep(interval_sec)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        logging.info("Started balance poller (coin=%s, interval=%ss).", coin, interval_sec)

    # ------------------------------------------------------------- Trading
    def open_market_order(
        self,
        side: str,
        qty: float,
        position_idx: int = 0,
        reduce_only: bool = False,
        order_link_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "category": self.category,
            "symbol": self.symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": reduce_only,
            "positionIdx": position_idx,
        }
        if order_link_id:
            payload["orderLinkId"] = order_link_id
        logging.info("[OPEN ORDER] %s", payload)
        resp = self.http.place_order(**payload)
        logging.info("[OPEN ORDER RESP] %s", resp)
        return resp

    def close_position(
        self,
        original_side: str,
        qty: float,
        position_idx: int = 0,
        order_link_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        opp_side = "Sell" if original_side == "Buy" else "Buy"
        logging.info("[CLOSE POSITION] original_side=%s -> %s (reduceOnly)", original_side, opp_side)
        return self.open_market_order(
            side=opp_side,
            qty=qty,
            position_idx=position_idx,
            reduce_only=True,
            order_link_id=order_link_id,
        )

    # ------------------------------------------------------------- Monitoring
    def fetch_position(self) -> Dict[str, Any]:
        resp = self.http.get_positions(category=self.category, symbol=self.symbol)
        self.latest_positions = resp
        logging.info("[POSITION] %s", resp)
        return resp

    def fetch_open_orders(self, open_only: bool = True, limit: int = 50) -> Dict[str, Any]:
        open_only_flag = 0 if open_only else 1
        resp = self.http.get_open_orders(
            category=self.category,
            symbol=self.symbol,
            openOnly=open_only_flag,
            limit=limit,
        )
        self.latest_open_orders = resp
        logging.info("[OPEN ORDERS] %s", resp)
        return resp

    def fetch_trade_history(self, limit: int = 50) -> Dict[str, Any]:
        resp = self.http.get_executions(
            category=self.category,
            symbol=self.symbol,
            limit=limit,
        )
        self.latest_trades = resp
        logging.info("[TRADE HISTORY] %s", resp)
        return resp

    # ------------------------------------------------------------- Shutdown
    def shutdown(self) -> None:
        self._stop_flag = True
        logging.info("Shutdown requested (balance poller will stop).")


def main():
        if API_KEY == "YOUR_API_KEY_HERE":
            raise SystemExit("Please set API_KEY / API_SECRET at top of file.")

        client = BybitPybitClient(
            api_key=API_KEY,
            api_secret=API_SECRET,
            symbol=SYMBOL,
            category=CATEGORY,
            account_type=ACCOUNT_TYPE,
            env=ENV,
        )

        client.start_private_streams()
        client.start_balance_poller(coin="USDT", interval_sec=3)

        time.sleep(5)

        try:
            client.open_market_order(side="Buy", qty=0.001)
        except Exception as exc:
            logging.exception("Failed to open order: %s", exc)

        for _ in range(3):
            try:
                client.fetch_position()
                client.fetch_open_orders(open_only=True, limit=10)
                client.fetch_trade_history(limit=10)
            except Exception as exc:
                logging.exception("Monitoring error: %s", exc)
            time.sleep(10)

        try:
            client.close_position(original_side="Buy", qty=0.001)
        except Exception as exc:
            logging.exception("Failed to close position: %s", exc)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            client.shutdown()
            logging.info("Exiting...")


if __name__ == "__main__":
    main()
