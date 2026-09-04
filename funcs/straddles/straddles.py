"""
Strategies engine for option spreads and straddles:
- Long Straddle (ATM Call + ATM Put)
- Bull Call Spread (Debit Call Spread)
- Bear Put Spread (Debit Put Spread)
- Bull Put Spread (Credit Put Spread)
- Bear Call Spread (Credit Call Spread)
- Iron Condor (Bull Put Spread + Bear Call Spread)
"""

from ..positions.orders import placeBuyorderLimit_, placeSellOrderLimit_
from ..positions.position import closeAPosition

def bull_call_spread(lower_call_symbol: str, higher_call_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bull Call Spread (Debit Spread):
    1. Buy the lower strike call (expensive leg)
    2. Sell the higher strike call (discount leg)
    """
    leg1_buy = placeBuyorderLimit_(symbol=lower_call_symbol, qty=qty, limit_price=buy_price)
    
    if leg1_buy.get("status") != "success":
        return {
            "status": "error",
            "reason": f"Failed to execute Leg 1 (Buy {lower_call_symbol}): {leg1_buy.get('reason')}"
        }

    leg2_sell = placeSellOrderLimit_(symbol=higher_call_symbol, qty=qty, limit_price=sell_price)
    
    # If Leg 2 fails, panic close Leg 1 to prevent directional exposure
    if leg2_sell.get("status") != "success":
        closeAPosition(symbol=lower_call_symbol, qty=qty)
        return {
            "status": "error",
            "reason": f"Leg 2 (Sell {higher_call_symbol}) failed: {leg2_sell.get('reason')}. Leg 1 closed for safety."
        }

    return {
        "status": "success",
        "strategy": "Bull Call Spread",
        "leg1": leg1_buy.get("order"),
        "leg2": leg2_sell.get("order")
    }


def bear_put_spread(higher_put_symbol: str, lower_put_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bear Put Spread (Debit Spread):
    1. Buy the higher strike put (expensive leg)
    2. Sell the lower strike put (discount leg)
    """
    leg1_buy = placeBuyorderLimit_(symbol=higher_put_symbol, qty=qty, limit_price=buy_price)
    
    if leg1_buy.get("status") != "success":
        return {
            "status": "error",
            "reason": f"Failed to execute Leg 1 (Buy {higher_put_symbol}): {leg1_buy.get('reason')}"
        }

    leg2_sell = placeSellOrderLimit_(symbol=lower_put_symbol, qty=qty, limit_price=sell_price)
    
    if leg2_sell.get("status") != "success":
        closeAPosition(symbol=higher_put_symbol, qty=qty)
        return {
            "status": "error",
            "reason": f"Leg 2 (Sell {lower_put_symbol}) failed: {leg2_sell.get('reason')}. Leg 1 closed for safety."
        }

    return {
        "status": "success",
        "strategy": "Bear Put Spread",
        "leg1": leg1_buy.get("order"),
        "leg2": leg2_sell.get("order")
    }


def bull_put_spread(lower_put_symbol: str, higher_put_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bull Put Spread (Credit Spread):
    1. Buy the lower strike put (protective long put)
    2. Sell the higher strike put (income short put)
    """
    # Buy protection first
    leg1_buy = placeBuyorderLimit_(symbol=lower_put_symbol, qty=qty, limit_price=buy_price)
    if leg1_buy.get("status") != "success":
        return {
            "status": "error",
            "reason": f"Failed to execute Leg 1 (Buy {lower_put_symbol}): {leg1_buy.get('reason')}"
        }

    leg2_sell = placeSellOrderLimit_(symbol=higher_put_symbol, qty=qty, limit_price=sell_price)
    if leg2_sell.get("status") != "success":
        closeAPosition(symbol=lower_put_symbol, qty=qty)
        return {
            "status": "error",
            "reason": f"Leg 2 (Sell {higher_put_symbol}) failed: {leg2_sell.get('reason')}. Leg 1 closed for safety."
        }

    return {
        "status": "success",
        "strategy": "Bull Put Spread",
        "leg1": leg1_buy.get("order"),
        "leg2": leg2_sell.get("order")
    }


def bear_call_spread(lower_call_symbol: str, higher_call_symbol: str, sell_price: float, buy_price: float, qty: int):
    """
    Bear Call Spread (Credit Spread):
    1. Buy the higher strike call (protective long call)
    2. Sell the lower strike call (income short call)
    """
    leg1_buy = placeBuyorderLimit_(symbol=higher_call_symbol, qty=qty, limit_price=buy_price)
    if leg1_buy.get("status") != "success":
        return {
            "status": "error",
            "reason": f"Failed to execute Leg 1 (Buy {higher_call_symbol}): {leg1_buy.get('reason')}"
        }

    leg2_sell = placeSellOrderLimit_(symbol=lower_call_symbol, qty=qty, limit_price=sell_price)
    if leg2_sell.get("status") != "success":
        closeAPosition(symbol=higher_call_symbol, qty=qty)
        return {
            "status": "error",
            "reason": f"Leg 2 (Sell {lower_call_symbol}) failed: {leg2_sell.get('reason')}. Leg 1 closed for safety."
        }

    return {
        "status": "success",
        "strategy": "Bear Call Spread",
        "leg1": leg1_buy.get("order"),
        "leg2": leg2_sell.get("order")
    }


def long_straddle(call_symbol: str, put_symbol: str, call_buy_price: float, put_buy_price: float, qty: int):
    """
    Long Straddle (Volatility Play):
    Buys both an At-The-Money (ATM) Call and an At-The-Money (ATM) Put.
    """
    try:
        # 1. Buy the Call leg
        call_buy = placeBuyorderLimit_(
            symbol=call_symbol,
            qty=qty,
            limit_price=call_buy_price
        )

        if call_buy.get("status") != "success":
            return {
                "status": "error",
                "reason": f"Failed to buy Call leg ({call_symbol}): {call_buy.get('reason')}"
            }

        # 2. Buy the Put leg
        put_buy = placeBuyorderLimit_(
            symbol=put_symbol,
            qty=qty,
            limit_price=put_buy_price
        )

        # Safety Check: If Put fails, liquidate Call immediately
        if put_buy.get("status") != "success":
            closeAPosition(symbol=call_symbol, qty=qty)
            return {
                "status": "error",
                "reason": f"Put leg ({put_symbol}) failed: {put_buy.get('reason')}. Call leg closed for safety."
            }

        return {
            "status": "success",
            "strategy": "Long Straddle",
            "call_leg": call_buy.get("order"),
            "put_leg": put_buy.get("order")
        }

    except Exception as error:
        return {
            "status": "error",
            "reason": str(error)
        }


def iron_condor(
    put_buy_symbol: str,
    put_sell_symbol: str,
    call_sell_symbol: str,
    call_buy_symbol: str,
    put_buy_price: float,
    put_sell_price: float,
    call_sell_price: float,
    call_buy_price: float,
    qty: int
):
    """
    Iron Condor: Combination of Bull Put Spread and Bear Call Spread.
    """
    try:
        # Leg 1 & 2: Bull Put Spread (Wing below market)
        put_spread = bull_put_spread(
            lower_put_symbol=put_buy_symbol,
            higher_put_symbol=put_sell_symbol,
            buy_price=put_buy_price,
            sell_price=put_sell_price,
            qty=qty
        )

        if put_spread.get("status") != "success":
            return {
                "status": "error",
                "reason": f"Iron Condor Put wing failed: {put_spread.get('reason')}"
            }

        # Leg 3 & 4: Bear Call Spread (Wing above market)
        call_spread = bear_call_spread(
            lower_call_symbol=call_sell_symbol,
            higher_call_symbol=call_buy_symbol,
            sell_price=call_sell_price,
            buy_price=call_buy_price,
            qty=qty
        )

        if call_spread.get("status") != "success":
            # Clean up put spread wings
            closeAPosition(symbol=put_buy_symbol, qty=qty)
            closeAPosition(symbol=put_sell_symbol, qty=qty)
            return {
                "status": "error",
                "reason": f"Iron Condor Call wing failed: {call_spread.get('reason')}. Put wing rolled back."
            }

        return {
            "status": "success",
            "strategy": "Iron Condor",
            "put_spread": put_spread,
            "call_spread": call_spread
        }

    except Exception as error:
        return {
            "status": "error",
            "reason": str(error)
        }

