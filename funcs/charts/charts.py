import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from urls.urls import APIKEY, APISECRET

DATA_OPTIONS_URL = "https://data.alpaca.markets/v1beta1/options"

def get_headers():
    return {
        "accept": "application/json",
        "APCA-API-KEY-ID": APIKEY,
        "APCA-API-SECRET-KEY": APISECRET
    }

def get_latest_option_quotes(symbols: str | list[str] = None, feed: str = "opra"):
    """
    Fetches the latest quotes for options contracts using the real Alpaca API keys.
    Endpoint: https://data.alpaca.markets/v1beta1/options/quotes/latest
    """
    url = f"{DATA_OPTIONS_URL}/quotes/latest?feed={feed}"
    if symbols:
        if isinstance(symbols, list):
            symbols_str = ",".join(symbols)
        else:
            symbols_str = symbols
        url += f"&symbols={symbols_str}"

    headers = get_headers()
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return {
            "status": "success",
            "data": response.json()
        }
    else:
        # If OPRA feed is restricted on free paper tier, try falling back to indicative feed
        if feed == "opra" and response.status_code in (401, 403, 422):
            fallback_url = f"{DATA_OPTIONS_URL}/quotes/latest?feed=indicative"
            if symbols:
                fallback_url += f"&symbols={symbols_str}"
            fb_resp = requests.get(fallback_url, headers=headers)
            if fb_resp.status_code == 200:
                return {
                    "status": "success",
                    "data": fb_resp.json()
                }

        return {
            "status": "error",
            "code": response.status_code,
            "reason": response.text
        }

def get_option_bars(symbols: str | list[str], timeframe: str = "1Hour", feed: str = "opra", limit: int = 50):
    """
    Fetches historical candle bars for option contracts via Alpaca REST API.
    """
    if isinstance(symbols, list):
        symbols_str = ",".join(symbols)
    else:
        symbols_str = symbols

    url = f"{DATA_OPTIONS_URL}/bars?symbols={symbols_str}&timeframe={timeframe}&feed={feed}&limit={limit}"
    headers = get_headers()
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return {
            "status": "success",
            "data": response.json()
        }
    else:
        return {
            "status": "error",
            "code": response.status_code,
            "reason": response.text
        }

if __name__ == "__main__":
    url = "https://data.alpaca.markets/v1beta1/options/quotes/latest?feed=opra"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": APIKEY,
        "APCA-API-SECRET-KEY": APISECRET
    }

    response = requests.get(url, headers=headers)
    print(response.text)
