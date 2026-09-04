"""
    So this file is for me to write the function for the 
    bull call spread, bear put spread, iron condor, or long straddle 
    so that the erm MCP can call it as it wants you know what i mean
"""

from ..positions.orders import placeBuyorderLimit_, placeSellOrderLimit_
from ..positions.position import closeAPosition

def bull_call_spread(lower_call_symbol: str, higher_call_symbol: str, buy_price: float, sell_price: float, qty: int):
    # BULL CALL = BUY LOW (Lower Strike), SELL HIGH (Higher Strike)
    # 1. Buy the lower strike call first (The expensive leg)
    leg1_buy = placeBuyorderLimit_(symbol=lower_call_symbol, qty=qty, limit_price=buy_price)
    
    if leg1_buy["status"] == "success":
        # 2. Sell the higher strike call to get your discount
        leg2_sell = placeSellOrderLimit_(symbol=higher_call_symbol, qty=qty, limit_price=sell_price)
        
    # Safety Check: If Leg 2 fails to sell, your account is exposed. Panic close Leg 1!
    if "error" in [leg1_buy.get("status"), leg2_sell.get("status")]:
        if leg1_buy.get("status") == "success":
            closeAPosition(symbol=lower_call_symbol, qty=qty, percentage=100)
        return {"status": "error", "reason": "Spread execution failed. Cleaned up."}
        
    return {"status": "success"}



def bear_put_spread(higher_put_symbol: str, lower_put_symbol: str, buy_price: float, sell_price: float, qty: int):
    # BEAR PUT = BUY HIGH (Higher Strike), SELL LOW (Lower Strike)
    # 1. Buy the higher strike put first (The expensive leg)
    leg1_buy = placeBuyorderLimit_(symbol=higher_put_symbol, qty=qty, limit_price=buy_price)
    
    if leg1_buy["status"] == "success":
        # 2. Sell the lower strike put to get your discount
        leg2_sell = placeSellOrderLimit_(symbol=lower_put_symbol, qty=qty, limit_price=sell_price)
        
    # Safety Check: If Leg 2 fails, panic close Leg 1!
    if "error" in [leg1_buy.get("status"), leg2_sell.get("status")]:
        if leg1_buy.get("status") == "success":
            closeAPosition(symbol=higher_put_symbol, qty=qty, percentage=100)
        return {"status": "error", "reason": "Spread execution failed. Cleaned up."}
        
    return {"status": "success"}



def iron_condor():
    """
        This is the combination of both the bull_put and bear_put strategy
    """
    try:
        # Bull put if successfull it should place the bearput
        bull_put = bull_put_spread()
        
        if bull_put["status"] == "success":
            bear_put = bear_put_spread()

        return {
            "status":"success",
            "result":{
                "bull_put":bull_put,
                "bear_put":bear_put
            }
        }
            
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
