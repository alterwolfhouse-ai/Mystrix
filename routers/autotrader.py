from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone
import threading
import time
from decimal import Decimal, ROUND_DOWN

import requests
from fastapi import APIRouter, HTTPException

try:
    from pybit.unified_trading import HTTP as BYBIT_HTTP  # type: ignore
except Exception:
    BYBIT_HTTP = None

from schemas.autotrader import AutoTraderBalanceRequest, AutoTraderOrderRequest, AutoTraderDemoRequest, AutoTraderTradingStopRequest
from engine.bybit_data import fetch_ticker, fetch_instrument_info, BYBIT_MAINNET, BYBIT_TESTNET


router = APIRouter(tags=["autotrader"])


@router.get("/autotrader/public_ip")
def autotrader_public_ip():
    try:
        resp = requests.get("https://api.ipify.org?format=json", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {"ip": data.get("ip")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to determine public IP: {exc}")


def _resolve_env(base_url: str | None, environment: str | None) -> tuple[bool, bool]:
    """Return (demo, testnet)."""
    env = (environment or "").strip().lower()
    base = (base_url or "").strip()
    if "demo" in base:
        return True, False
    if "testnet" in base:
        return False, True
    if env in ("demo", "paper"):
        return True, False
    if env in ("testnet",):
        return False, True
    return False, False


def _resolve_price_base_url(base_url: str | None, environment: str | None) -> str:
    env = (environment or "").strip().lower()
    base = (base_url or "").strip()
    if base and base != "paper":
        return base
    if env == "demo":
        return "https://api-demo.bybit.com"
    if env == "testnet":
        return BYBIT_TESTNET
    return BYBIT_MAINNET


def _dec(val: Any) -> Decimal:
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")


def _quantize_qty(qty: Decimal, step: Decimal | None) -> tuple[Decimal, int]:
    if not step or step <= 0:
        return qty, 8
    steps = (qty / step).to_integral_value(rounding=ROUND_DOWN)
    qty_q = steps * step
    precision = max(0, -step.as_tuple().exponent)
    return qty_q, precision


def _quantize_price(price: Decimal, tick: Decimal | None) -> tuple[Decimal, int]:
    if not tick or tick <= 0:
        return price, 8
    steps = (price / tick).to_integral_value(rounding=ROUND_DOWN)
    price_q = steps * tick
    precision = max(0, -tick.as_tuple().exponent)
    return price_q, precision


def _format_qty(qty: Decimal, precision: int) -> str:
    return format(qty, f".{precision}f")


def _format_price(symbol: str, price: float | None, base_url: str) -> str | None:
    if price is None:
        return None
    if price <= 0:
        return "0"
    info = fetch_instrument_info(symbol, category="linear", base_url=base_url)
    price_filter = info.get("priceFilter", {}) if isinstance(info, dict) else {}
    tick = _dec(price_filter.get("tickSize"))
    price_dec = _dec(price)
    price_dec, precision = _quantize_price(price_dec, tick if tick > 0 else None)
    return _format_qty(price_dec, precision)


def _apply_qty_filters(symbol: str, qty: float, price_used: float | None, base_url: str) -> tuple[str, float | None]:
    info = fetch_instrument_info(symbol, category="linear", base_url=base_url)
    lot = info.get("lotSizeFilter", {}) if isinstance(info, dict) else {}
    min_qty = _dec(lot.get("minOrderQty"))
    max_qty = _dec(lot.get("maxOrderQty"))
    step = _dec(lot.get("qtyStep"))
    min_notional = _dec(lot.get("minNotionalValue") or lot.get("minNotional"))

    qty_dec = _dec(qty)
    qty_dec, precision = _quantize_qty(qty_dec, step if step > 0 else None)

    if min_qty > 0 and qty_dec < min_qty:
        raise HTTPException(status_code=400, detail=f"Qty below min ({min_qty})")
    if max_qty > 0 and qty_dec > max_qty:
        qty_dec = max_qty

    if min_notional > 0:
        price = price_used
        if not price:
            ticker = fetch_ticker(symbol, category="linear", base_url=base_url)
            try:
                price = float(ticker.get("lastPrice") or 0)
            except (TypeError, ValueError):
                price = None
        if price and price > 0:
            notional = qty_dec * _dec(price)
            if notional < min_notional:
                raise HTTPException(status_code=400, detail=f"Notional below min ({min_notional})")
        else:
            price = price_used
        price_used = price

    qty_str = _format_qty(qty_dec, precision)
    return qty_str, price_used


def _is_success(resp: Dict[str, Any]) -> bool:
    code = resp.get("retCode")
    return code in (0, "0", None)


def _raise_if_error(resp: Dict[str, Any], context: str) -> None:
    if _is_success(resp):
        return
    code = resp.get("retCode")
    msg = resp.get("retMsg") or "Unknown error"
    raise HTTPException(status_code=400, detail=f"{context} failed: {msg} (code {code})")


def _place_order_with_fallback(client: Any, params: Dict[str, Any]) -> tuple[Dict[str, Any], int | None]:
    resp = client.place_order(**params)
    if _is_success(resp):
        return resp, params.get("positionIdx")
    msg = str(resp.get("retMsg") or "")
    if "position idx" in msg.lower() and "positionIdx" not in params:
        alt_idx = 1 if params.get("side") == "Buy" else 2
        retry = dict(params)
        retry["positionIdx"] = alt_idx
        resp_retry = client.place_order(**retry)
        if _is_success(resp_retry):
            return resp_retry, alt_idx
        _raise_if_error(resp_retry, "Order")
    _raise_if_error(resp, "Order")
    return resp, params.get("positionIdx")


def _set_trading_stop_with_fallback(client: Any, params: Dict[str, Any], side: str | None) -> tuple[Dict[str, Any], int | None]:
    resp = client.set_trading_stop(**params)
    if _is_success(resp):
        return resp, params.get("positionIdx")
    msg = str(resp.get("retMsg") or "")
    if "position idx" in msg.lower() and "positionIdx" not in params:
        if side:
            side_val = side.strip().lower()
            alt_idx = 1 if side_val in ("buy", "long") else (2 if side_val in ("sell", "short") else None)
        else:
            alt_idx = None
        if alt_idx is not None:
            retry = dict(params)
            retry["positionIdx"] = alt_idx
            resp_retry = client.set_trading_stop(**retry)
            if _is_success(resp_retry):
                return resp_retry, alt_idx
            _raise_if_error(resp_retry, "Trading stop")
    _raise_if_error(resp, "Trading stop")
    return resp, params.get("positionIdx")


def _resolve_futures_account_types(account_type: str | None) -> list[str]:
    """Force futures-only account types."""
    if not account_type:
        return ["CONTRACT", "UNIFIED"]
    val = account_type.strip().lower()
    if val in ("contract", "futures", "future"):
        return ["CONTRACT", "UNIFIED"]
    if val in ("unified",):
        return ["UNIFIED", "CONTRACT"]
    # ignore spot when futures-only is requested
    return ["CONTRACT", "UNIFIED"]


@router.post("/autotrader/balance")
def autotrader_balance(req: AutoTraderBalanceRequest):
    if BYBIT_HTTP is None:
        raise HTTPException(status_code=400, detail="pybit not installed")
    try:
        demo, testnet = _resolve_env(req.base_url, req.environment)
        client = BYBIT_HTTP(
            demo=demo,
            testnet=testnet,
            api_key=req.api_key,
            api_secret=req.api_secret,
        )
        acct_candidates = _resolve_futures_account_types(req.account_type)
        last_err = None
        for acct_type in acct_candidates:
            try:
                resp = client.get_wallet_balance(accountType=acct_type, coin="USDT")
                total_equity = 0.0
                breakdown: List[Dict[str, Any]] = []
                lst = resp.get("result", {}).get("list", [])
                if lst:
                    total_equity = float(lst[0].get("totalEquity", 0.0))
                    coin_details = lst[0].get("coin", [])
                    for c in coin_details:
                        breakdown.append(
                            {
                                "asset": c.get("coin"),
                                "amount": float(c.get("equity", 0.0)),
                                "price_usdt": 1.0 if c.get("coin", "").upper() in ("USDT", "USD") else None,
                                "usdt_value": float(c.get("equity", 0.0)),
                            }
                        )
                return {
                    "balance": total_equity,
                    "breakdown": breakdown,
                    "raw": resp,
                    "account_type_used": acct_type,
                    "environment": "demo" if demo else ("testnet" if testnet else "live"),
                }
            except Exception as err:
                last_err = err
                continue
        raise HTTPException(status_code=400, detail=f"Unable to fetch balance via Bybit futures wallet: {last_err}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch balance: {exc}")


@router.post("/autotrader/positions")
def autotrader_positions(req: AutoTraderBalanceRequest):
    if BYBIT_HTTP is None:
        raise HTTPException(status_code=400, detail="pybit not installed")
    try:
        demo, testnet = _resolve_env(req.base_url, req.environment)
        client = BYBIT_HTTP(
            demo=demo,
            testnet=testnet,
            api_key=req.api_key,
            api_secret=req.api_secret,
        )
        resp = client.get_positions(category="linear", settleCoin="USDT")
        items = resp.get("result", {}).get("list", []) or []
        def _num(val: Any) -> float | None:
            try:
                out = float(val)
            except (TypeError, ValueError):
                return None
            return out

        positions: List[Dict[str, Any]] = []
        for pos in items:
            try:
                size = float(pos.get("size") or 0)
            except (TypeError, ValueError):
                size = 0.0
            if size == 0.0:
                continue
            symbol = str(pos.get("symbol") or "")
            symbol = symbol.upper()
            if symbol.endswith("USDT") and "/" not in symbol:
                symbol = f"{symbol[:-4]}/USDT"
            entry_raw = pos.get("avgPrice") or pos.get("entryPrice") or 0
            try:
                entry_price = float(entry_raw)
            except (TypeError, ValueError):
                entry_price = 0.0
            pnl_raw = pos.get("unrealisedPnl") or pos.get("unrealisedProfit") or 0
            try:
                unrealized = float(pnl_raw)
            except (TypeError, ValueError):
                unrealized = 0.0
            lev_raw = pos.get("leverage") or pos.get("positionLeverage")
            leverage = _num(lev_raw)
            if leverage is not None and leverage <= 0:
                leverage = None
            stop_loss = _num(pos.get("stopLoss") or pos.get("stopLossPrice"))
            take_profit = _num(pos.get("takeProfit") or pos.get("takeProfitPrice"))
            last_price = _num(pos.get("markPrice") or pos.get("lastPrice") or pos.get("marketPrice"))
            side = str(pos.get("side") or "").lower()
            created = pos.get("createdTime") or pos.get("updatedTime") or 0
            opened_at = None
            try:
                ts = int(created)
                opened_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
            except Exception:
                opened_at = None
            positions.append(
                {
                    "symbol": symbol,
                    "side": "long" if side == "buy" else ("short" if side == "sell" else side),
                    "size": size,
                    "entry_price": entry_price,
                    "unrealized_pnl": unrealized,
                    "leverage": leverage,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "last_price": last_price,
                    "opened_at": opened_at,
                }
            )
        return {"positions": positions, "raw": resp}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch positions: {exc}")


@router.post("/autotrader/trading_stop")
def autotrader_trading_stop(req: AutoTraderTradingStopRequest):
    if BYBIT_HTTP is None:
        raise HTTPException(status_code=400, detail="pybit not installed")
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Trading stop confirm flag required")
    symbol = (req.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol required")
    if "/" in symbol:
        symbol = symbol.replace("/", "")
    if req.stop_loss is None and req.take_profit is None:
        raise HTTPException(status_code=400, detail="stop_loss or take_profit required")

    base_url = _resolve_price_base_url(req.base_url, req.environment)
    stop_loss = _format_price(symbol, req.stop_loss, base_url) if req.stop_loss is not None else None
    take_profit = _format_price(symbol, req.take_profit, base_url) if req.take_profit is not None else None
    params: Dict[str, Any] = {"category": "linear", "symbol": symbol}
    if stop_loss is not None:
        params["stopLoss"] = stop_loss
    if take_profit is not None:
        params["takeProfit"] = take_profit
    if req.position_idx is not None:
        params["positionIdx"] = req.position_idx

    try:
        demo, testnet = _resolve_env(req.base_url, req.environment)
        client = BYBIT_HTTP(
            demo=demo,
            testnet=testnet,
            api_key=req.api_key,
            api_secret=req.api_secret,
        )
        resp, position_idx_used = _set_trading_stop_with_fallback(client, params, req.side)
        return {
            "ok": True,
            "result": resp,
            "position_idx_used": position_idx_used,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to set trading stop: {exc}")


@router.post("/autotrader/order")
def autotrader_order(req: AutoTraderOrderRequest):
    if BYBIT_HTTP is None:
        raise HTTPException(status_code=400, detail="pybit not installed")
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Order confirm flag required")
    symbol = (req.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol required")
    if "/" in symbol:
        symbol = symbol.replace("/", "")
    side = (req.side or "").strip().lower()
    if side in ("buy", "long"):
        side_val = "Buy"
    elif side in ("sell", "short"):
        side_val = "Sell"
    else:
        raise HTTPException(status_code=400, detail="Side must be buy/sell/long/short")
    order_type = (req.order_type or "Market").strip().title()
    qty = req.qty
    price_used = None
    if qty is None:
        if req.notional_usdt is None:
            raise HTTPException(status_code=400, detail="qty or notional_usdt required")
        base_url = _resolve_price_base_url(req.base_url, req.environment)
        ticker = fetch_ticker(symbol, category="linear", base_url=base_url)
        last_price = None
        try:
            last_price = float(ticker.get("lastPrice") or 0)
        except (TypeError, ValueError):
            last_price = None
        if not last_price or last_price <= 0:
            raise HTTPException(status_code=400, detail="Unable to fetch last price for sizing")
        qty = float(req.notional_usdt) / last_price
        price_used = last_price
    base_url = _resolve_price_base_url(req.base_url, req.environment)
    qty_str, price_used = _apply_qty_filters(symbol, float(qty), price_used, base_url)

    try:
        demo, testnet = _resolve_env(req.base_url, req.environment)
        client = BYBIT_HTTP(
            demo=demo,
            testnet=testnet,
            api_key=req.api_key,
            api_secret=req.api_secret,
        )
        params: Dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "side": side_val,
            "orderType": order_type,
            "qty": qty_str,
            "reduceOnly": req.reduce_only,
        }
        if req.position_idx is not None:
            params["positionIdx"] = req.position_idx
        resp, position_idx_used = _place_order_with_fallback(client, params)
        return {
            "ok": True,
            "order": resp,
            "qty": qty_str,
            "price_used": price_used,
            "position_idx_used": position_idx_used,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to place order: {exc}")


@router.post("/autotrader/demo_trade")
def autotrader_demo_trade(req: AutoTraderDemoRequest):
    if BYBIT_HTTP is None:
        raise HTTPException(status_code=400, detail="pybit not installed")
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Order confirm flag required")
    symbol = (req.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol required")
    if "/" in symbol:
        symbol = symbol.replace("/", "")
    side = (req.side or "").strip().lower()
    if side in ("buy", "long"):
        side_val = "Buy"
    elif side in ("sell", "short"):
        side_val = "Sell"
    else:
        raise HTTPException(status_code=400, detail="Side must be buy/sell/long/short")
    order_type = "Market"

    qty = req.qty
    price_used = None
    if qty is None:
        if req.notional_usdt is None:
            raise HTTPException(status_code=400, detail="qty or notional_usdt required")
        base_url = _resolve_price_base_url(req.base_url, req.environment)
        ticker = fetch_ticker(symbol, category="linear", base_url=base_url)
        last_price = None
        try:
            last_price = float(ticker.get("lastPrice") or 0)
        except (TypeError, ValueError):
            last_price = None
        if not last_price or last_price <= 0:
            raise HTTPException(status_code=400, detail="Unable to fetch last price for sizing")
        qty = float(req.notional_usdt) / last_price
        price_used = last_price
    base_url = _resolve_price_base_url(req.base_url, req.environment)
    qty_str, price_used = _apply_qty_filters(symbol, float(qty), price_used, base_url)

    try:
        demo, testnet = _resolve_env(req.base_url, req.environment)
        client = BYBIT_HTTP(
            demo=demo,
            testnet=testnet,
            api_key=req.api_key,
            api_secret=req.api_secret,
        )
        params: Dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "side": side_val,
            "orderType": order_type,
            "qty": qty_str,
            "reduceOnly": False,
        }
        resp, position_idx_used = _place_order_with_fallback(client, params)

        def _close_after_delay():
            try:
                time.sleep(max(1, int(req.hold_seconds)))
                close_side = "Sell" if side_val == "Buy" else "Buy"
                close_params: Dict[str, Any] = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": close_side,
                    "orderType": "Market",
                    "qty": qty_str,
                    "reduceOnly": True,
                }
                if position_idx_used is not None:
                    close_params["positionIdx"] = position_idx_used
                close_resp = client.place_order(**close_params)
                if not _is_success(close_resp):
                    _raise_if_error(close_resp, "Close order")
            except Exception as exc:
                try:
                    with open("server.err.log", "a", encoding="utf-8") as fh:
                        fh.write(f"[DEMO_LIVE] close failed {symbol}: {exc}\n")
                except Exception:
                    pass

        threading.Thread(target=_close_after_delay, daemon=True).start()

        return {
            "ok": True,
            "open_order": resp,
            "qty": qty_str,
            "price_used": price_used,
            "position_idx_used": position_idx_used,
            "close_in": int(req.hold_seconds),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to place demo trade: {exc}")
