import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT
import requests

def closeAPosition(symbol: str, qty: int, percentage: int):
    try:

        url = f"https://paper-api.alpaca.markets/v2/positions/{symbol}?qty={qty}&percentage={percentage}"

        headers = {"accept": "application/json"}

        response = requests.delete(url, headers=headers)

        return {
            "status":"success",
            "result":response.text 
        }

    except Exception as error:
        return {
            "status":"error",
            "reason": str(error)
        }

