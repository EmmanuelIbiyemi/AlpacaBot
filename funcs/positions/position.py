import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT, APIKEY, APISECRET

def _get_headers():
    return {
        "accept": "application/json",
        "APCA-API-KEY-ID": APIKEY,
        "APCA-API-SECRET-KEY": APISECRET
    }

def getPositions():
    """
    Fetches all open positions (equities and options) from Alpaca.
    """
    try:
        url = f"{ENDPOINT}/positions"
        response = requests.get(url, headers=_get_headers())
        if response.status_code == 200:
            return {
                "status": "success",
                "positions": response.json()
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

def closeAPosition(symbol: str, qty: int | str = None, percentage: int | str = None):
    """
    Closes an open position by symbol.
    Pass either qty or percentage (not both). Defaults to 100% liquidation.
    """
    try:
        symbol = symbol.upper()
        if qty is not None:
            url = f"{ENDPOINT}/positions/{symbol}?qty={qty}"
        else:
            pct = percentage if percentage is not None else 100
            url = f"{ENDPOINT}/positions/{symbol}?percentage={pct}"

        response = requests.delete(url, headers=_get_headers())

        if response.status_code in (200, 204):
            return {
                "status": "success",
                "msg": f"Position for {symbol} closed successfully",
                "result": response.json() if response.text else {}
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


