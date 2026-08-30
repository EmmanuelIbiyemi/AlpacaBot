"""
    So this file is for me to write the function for the 
    bull call spread, bear put spread, iron condor, or long straddle 
    so that the erm MCP can call it as it wants you know what i mean
"""

from ..positions.orders import placeBuyorder_Stop, placeSellOrder_Stop, placeBuyorderLimit_, placeSellOrderLimit_
from ..positions.position import closeAPosition

def bull_call_spread():
    try:
        pass 

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }


def bear_put_spread():
    try:

        pass 

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }


def iron_condor():
    try:

        pass 

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }

def long_straddle(call_buy_price: int , call_put_price: int, symbol: str, qty: int):
    try:
         
        #  This is the first_leg buying the call
        call_buy = placeBuyorderLimit_(
            symbol=symbol,
            qty=qty,
            limit_price=call_buy_price
        )

        # 2. Only fire the Put leg if the Call leg successfully filled
        if call_buy.get("status") == "success":
            put_buy = placeBuyorderLimit_(
                symbol=symbol,
                qty=qty,
                limit_price=call_put_price
            )


        if (not call_buy or call_buy.get("status") == "error" or 
            not put_buy or put_buy.get("status") == "error"):
            """
                The plan will be just to close the position quickly since one position is missing i mean fill it up later will just be filled at a bad price
            """

            closeAPosition(
                symbol=symbol , 
                qty=qty , 
                percentage=100
            )

            return {
                "status": "error",
                "reaosn":"One order was just placed for the long straddle"
            }
        
        return {
            "status":"success",
            "reason":"Long straddle placed successfully"
        }

    except Exception as error:
        return {
            "status":"error",
            "reason":str(error)
        }
