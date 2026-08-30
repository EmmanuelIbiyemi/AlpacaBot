import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT, APIKEY, APISECRET
print("Endpoint: ", ENDPOINT)
import requests

def placeBuyorderLimit_(symbol: str, qty: str, limit_price: str):
    try:
        url = ENDPOINT + "/orders"
        payload = {
            "limit_price": limit_price,
            "qty": qty,
            "side": "buy",
            "symbol": symbol,
            "time_in_force": "gtc",
            "type": "limit"
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "APCA-API-KEY-ID": APIKEY,
            "APCA-API-SECRET-KEY": APISECRET
        }

        response = requests.post(url, json=payload, headers=headers)

        return {
            "status":"success",
            "msg":"order placed successfully"
        }

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }

def placeSellOrderLimit_(symbol: str, qty: str, limit_price: str):
    try:
        url = ENDPOINT

        payload = {
            "limit_price": limit_price,
            "qty": qty,
            "side": "sell",
            "symbol": symbol,
            "time_in_force": "gtc",
            "type": "limit"
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "APCA-API-KEY-ID": APIKEY,
            "APCA-API-SECRET-KEY": APISECRET
        }

        response = requests.post(url, json=payload, headers=headers)

        return {
            "status":"success",
            "msg":"order placed successfully"
        }

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }


def placeBuyorder_Stop(symbol: str, qty: int, stop_price: str):
    try:
        url = ENDPOINT

        payload = {
            "stop_price": stop_price,
            "qty": qty,
            "side": "buy",
            "symbol": symbol,
            "time_in_force": "gtc",
            "type": "stop"
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "APCA-API-KEY-ID": APIKEY,
            "APCA-API-SECRET-KEY": APISECRET
        }

        response = requests.post(url, json=payload, headers=headers)

        return {
            "status":"success",
            "msg":"order placed successfully"
        }

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }


def placeSellorderStop(symbol: str, qty: str, stop_price: str):
    try:
        url = ENDPOINT

        payload = {
            "stop_price": stop_price,
            "qty": qty,
            "side": "sell",
            "symbol": symbol,
            "time_in_force": "gtc",
            "type": "stop"
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "APCA-API-KEY-ID": APIKEY,
            "APCA-API-SECRET-KEY": APISECRET
        }

        response = requests.post(url, json=payload, headers=headers)

        return {
            "status":"success",
            "msg":"order placed successfully"
        }

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }

