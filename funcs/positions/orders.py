import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT, APIKEY, APISECRET

def _get_headers():
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "APCA-API-KEY-ID": APIKEY,
        "APCA-API-SECRET-KEY": APISECRET
    }

def place_order(symbol: str, qty: int | str, side: str, order_type: str = "limit", limit_price: float | str = None, stop_price: float | str = None, time_in_force: str = "day"):
    """
    Submits an equity or option order to Alpaca and returns detailed order info or error.
    """
    try:
        url = f"{ENDPOINT}/orders"
        payload = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": time_in_force
        }

        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        if stop_price is not None:
            payload["stop_price"] = str(stop_price)

        response = requests.post(url, json=payload, headers=_get_headers())

        if response.status_code in (200, 201):
            return {
                "status": "success",
                "msg": f"{side.upper()} order placed successfully",
                "order": response.json()
            }
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "reason": response.text
            }
    except Exception as error:
        return {
            "status": "error",
            "reason": str(error)
        }

def placeBuyorderLimit_(symbol: str, qty: int | str, limit_price: float | str):
    return place_order(symbol=symbol, qty=qty, side="buy", order_type="limit", limit_price=limit_price)

def placeSellOrderLimit_(symbol: str, qty: int | str, limit_price: float | str):
    return place_order(symbol=symbol, qty=qty, side="sell", order_type="limit", limit_price=limit_price)

def placeBuyorder_Stop(symbol: str, qty: int | str, stop_price: float | str):
    return place_order(symbol=symbol, qty=qty, side="buy", order_type="stop", stop_price=stop_price)

def placeSellorderStop(symbol: str, qty: int | str, stop_price: float | str):
    return place_order(symbol=symbol, qty=qty, side="sell", order_type="stop", stop_price=stop_price)

def place_mleg_order(legs: list, qty: int | str = 1, limit_price: float | str = None, order_type: str = "limit", time_in_force: str = "day"):
    """
    Submits an atomic Multi-Leg (MLeg) order to Alpaca.
    Bypasses naked short margin errors by bundling all legs simultaneously.
    legs: [{"symbol": "...", "ratio_qty": "1", "side": "buy"|"sell"}, ...]
    """
    try:
        url = f"{ENDPOINT}/orders"
        formatted_legs = []
        for leg in legs:
            formatted_legs.append({
                "symbol": leg["symbol"].upper(),
                "ratio_qty": str(leg.get("ratio_qty", 1)),
                "side": leg["side"].lower()
            })

        payload = {
            "order_class": "mleg",
            "qty": str(qty),
            "type": order_type.lower(),
            "time_in_force": time_in_force,
            "legs": formatted_legs
        }
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)

        response = requests.post(url, json=payload, headers=_get_headers())
        if response.status_code in (200, 201):
            return {
                "status": "success",
                "msg": "Multi-leg (MLeg) order placed successfully",
                "order": response.json()
            }
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "reason": response.text
            }
    except Exception as error:
        return {
            "status": "error",
            "reason": str(error)
        }



