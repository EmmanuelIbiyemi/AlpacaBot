"""
Strategies engine for option spreads and straddles using Alpaca's Multi-Leg (MLeg) API:
- Iron Condor (4 legs bundled in a single atomic order)
- Bull Call Spread (2 legs bundled)
- Bear Put Spread (2 legs bundled)
- Bull Put Spread (2 legs bundled)
- Bear Call Spread (2 legs bundled)
- Long Straddle (2 legs bundled)
"""

from ..positions.orders import placeBuyorderLimit_, placeSellOrderLimit_, place_mleg_order
from ..positions.position import closeAPosition

def bull_call_spread(lower_call_symbol: str, higher_call_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bull Call Spread: Bundled as a 2-leg atomic MLeg order.
    1. Buy Lower Call (expensive)
    2. Sell Higher Call (discount)
    """
    legs = [
        {"symbol": lower_call_symbol, "side": "buy", "ratio_qty": "1"},
        {"symbol": higher_call_symbol, "side": "sell", "ratio_qty": "1"}
    ]
    net_debit = round(max(buy_price - sell_price, 0.05), 2)
    print(f"📦 Submitting Bull Call Spread MLeg: Buy {lower_call_symbol} / Sell {higher_call_symbol} | Net: ${net_debit}")
    return place_mleg_order(legs=legs, qty=qty, limit_price=net_debit, order_type="limit")


def bear_put_spread(higher_put_symbol: str, lower_put_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bear Put Spread: Bundled as a 2-leg atomic MLeg order.
    1. Buy Higher Put (expensive)
    2. Sell Lower Put (discount)
    """
    legs = [
        {"symbol": higher_put_symbol, "side": "buy", "ratio_qty": "1"},
        {"symbol": lower_put_symbol, "side": "sell", "ratio_qty": "1"}
    ]
    net_debit = round(max(buy_price - sell_price, 0.05), 2)
    print(f"📦 Submitting Bear Put Spread MLeg: Buy {higher_put_symbol} / Sell {lower_put_symbol} | Net: ${net_debit}")
    return place_mleg_order(legs=legs, qty=qty, limit_price=net_debit, order_type="limit")


def bull_put_spread(lower_put_symbol: str, higher_put_symbol: str, buy_price: float, sell_price: float, qty: int):
    """
    Bull Put Spread (Credit Spread): Bundled as a 2-leg atomic MLeg order.
    1. Buy Lower Put (protection)
    2. Sell Higher Put (income)
    """
    legs = [
        {"symbol": lower_put_symbol, "side": "buy", "ratio_qty": "1"},
        {"symbol": higher_put_symbol, "side": "sell", "ratio_qty": "1"}
    ]
    net_credit = round(max(sell_price - buy_price, 0.05), 2)
    print(f"📦 Submitting Bull Put Spread MLeg: Buy {lower_put_symbol} / Sell {higher_put_symbol} | Net: ${net_credit}")
    return place_mleg_order(legs=legs, qty=qty, limit_price=net_credit, order_type="limit")


def bear_call_spread(lower_call_symbol: str, higher_call_symbol: str, sell_price: float, buy_price: float, qty: int):
    """
    Bear Call Spread (Credit Spread): Bundled as a 2-leg atomic MLeg order.
    1. Sell Lower Call (income)
    2. Buy Higher Call (protection)
    """
    legs = [
        {"symbol": higher_call_symbol, "side": "buy", "ratio_qty": "1"},
        {"symbol": lower_call_symbol, "side": "sell", "ratio_qty": "1"}
    ]
    net_credit = round(max(sell_price - buy_price, 0.05), 2)
    print(f"📦 Submitting Bear Call Spread MLeg: Buy {higher_call_symbol} / Sell {lower_call_symbol} | Net: ${net_credit}")
    return place_mleg_order(legs=legs, qty=qty, limit_price=net_credit, order_type="limit")


def long_straddle(call_symbol: str, put_symbol: str, call_buy_price: float, put_buy_price: float, qty: int):
    """
    Long Straddle: Bundled as a 2-leg atomic MLeg order (ATM Call + ATM Put).
    """
    legs = [
        {"symbol": call_symbol, "side": "buy", "ratio_qty": "1"},
        {"symbol": put_symbol, "side": "buy", "ratio_qty": "1"}
    ]
    total_debit = round(call_buy_price + put_buy_price, 2)
    print(f"📦 Submitting Long Straddle MLeg: Buy {call_symbol} & Buy {put_symbol} | Net: ${total_debit}")
    return place_mleg_order(legs=legs, qty=qty, limit_price=total_debit, order_type="limit")


def iron_condor(
    put_buy_symbol: str,
    put_sell_symbol: str,
    call_sell_symbol: str,
    call_buy_symbol: str,
    put_buy_price: float = 0.5,
    put_sell_price: float = 1.0,
    call_sell_price: float = 1.0,
    call_buy_price: float = 0.5,
    qty: int = 1,
    limit_price: float = None
):
    """
    Iron Condor: Bundles all 4 contracts together into a SINGLE atomic Multi-Leg (MLeg) order.
    Bypasses naked short margin rejection because Alpaca sees long contracts protecting short contracts.
    
    Leg 1 (Long Put):  BUY lower strike put (protection)
    Leg 2 (Short Put): SELL higher strike put (income)
    Leg 3 (Short Call): SELL lower strike call (income)
    Leg 4 (Long Call): BUY higher strike call (protection)
    """
    try:
        legs = [
            {"symbol": put_buy_symbol, "side": "buy", "ratio_qty": "1"},
            {"symbol": put_sell_symbol, "side": "sell", "ratio_qty": "1"},
            {"symbol": call_sell_symbol, "side": "sell", "ratio_qty": "1"},
            {"symbol": call_buy_symbol, "side": "buy", "ratio_qty": "1"}
        ]

        # Calculate estimated net credit if not explicitly given
        if limit_price is None:
            net_credit = (put_sell_price + call_sell_price) - (put_buy_price + call_buy_price)
            limit_price = round(max(net_credit, 0.10), 2)

        print(f"\n📦 Submitting Single Atomic 4-Leg Iron Condor (MLeg) to Alpaca:")
        print(f"   • Leg 1 (Long Put):   BUY  {put_buy_symbol}")
        print(f"   • Leg 2 (Short Put):  SELL {put_sell_symbol}")
        print(f"   • Leg 3 (Short Call): SELL {call_sell_symbol}")
        print(f"   • Leg 4 (Long Call):  BUY  {call_buy_symbol}")
        print(f"   • Net Limit Price: ${limit_price} | Qty: {qty}")

        # Try limit MLeg first
        res = place_mleg_order(legs=legs, qty=qty, limit_price=limit_price, order_type="limit")
        if res.get("status") == "success":
            return {
                "status": "success",
                "strategy": "Iron Condor",
                "mleg_order": res.get("order")
            }
        else:
            # If limit is rejected due to pricing requirements, try market MLeg
            print(f"⚠️ Limit MLeg response: {res.get('reason')}. Trying Market MLeg...")
            mkt_res = place_mleg_order(legs=legs, qty=qty, order_type="market")
            if mkt_res.get("status") == "success":
                return {
                    "status": "success",
                    "strategy": "Iron Condor",
                    "mleg_order": mkt_res.get("order")
                }
            return res

    except Exception as error:
        return {
            "status": "error",
            "reason": str(error)
        }


