

import os
import sys
import json
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from mcp.server.mcpserver import MCPServer

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# URLs AND KEYS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from urls.urls import ENDPOINT, APIKEY, APISECRET
from funcs.positions.orders import place_order
from funcs.positions.position import getPositions, closeAPosition
from funcs.straddles.straddles import (
    bull_call_spread,
    bear_put_spread,
    bull_put_spread,
    bear_call_spread,
    long_straddle,
    iron_condor
)

mcp = MCPServer("AlpacaOptionsDesk")

# Initialize Alpaca Clients
API_KEY = APIKEY
SECRET_KEY = APISECRET
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

def _auth_headers():
    return {
        "accept": "application/json",
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    }

@mcp.tool()
def analyze_chart_for_options(symbol: str, lookback_days: int = 5) -> str:
    """
    Fetches 1-hour candle data from Alpaca, automatically calculates 
    highs/lows, hourly range, and recommends Put strategies or Long Straddles.
    """
    try:
        symbol = symbol.upper()
        # 1. Fetch 1-Hour Bar Candle Data from Alpaca
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=lookback_days)
        
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start_time,
            end=end_time
        )
        
        bars = data_client.get_stock_bars(request_params)
        df = bars.df.loc[symbol] # Convert to a clean Pandas DataFrame
        
        if df.empty:
            return f"No chart data returned for {symbol}."

        # 2. Extract Range Data & Find Highs/Lows
        recent_close = df['close'].iloc[-1]
        highest_high = df['high'].max()
        lowest_low = df['low'].min()
        
        # Calculate Hourly Ranges (High minus Low for each hour candle)
        df['hourly_range'] = df['high'] - df['low']
        avg_hourly_range = df['hourly_range'].mean()
        
        # Determine current Volatility Context (Is the range expanding or shrinking?)
        recent_hourly_range = df['hourly_range'].iloc[-5:].mean()
        high_volatility = recent_hourly_range > (avg_hourly_range * 1.2)

        # 3. Formulate Strategy Rules
        output = [
            f"=== 📊 CHART ANALYSIS FOR {symbol} (1-Hour Candles) ===",
            f"Current Spot Price: ${recent_close:.2f}",
            f"Recent Range High:  ${highest_high:.2f}",
            f"Recent Range Low:   ${lowest_low:.2f}",
            f"Average Hourly Trading Range: ${avg_hourly_range:.2f}\n",
            "=== ⚡ SCREENER STRATEGY RECOMMENDATIONS ==="
        ]

        # Scenario A: High Volatility / Breakout -> Long Straddle
        if high_volatility:
            output.append("🎯 STRATEGY MATCH: LONG STRADDLE (Volatility Play)")
            output.append("💡 Reason: Recent hourly ranges are expanding rapidly. The stock is breaking past normal structures.")
            output.append(f"🛠️ Execution Blueprint: Buy an At-The-Money (ATM) Call AND Put at Strike ${round(recent_close)}.")
            output.append("⚠️ Risk: Total loss of premium if the price stays completely flat.")

        # Scenario B: Near Range High -> Put Strategies
        elif recent_close >= (highest_high - (avg_hourly_range * 2)):
            output.append("🎯 STRATEGY MATCH: BEARISH PUT PLAY (Overextended Near Highs)")
            output.append("💡 Reason: Spot price is testing upper resistance limits. Upside momentum is slowing.")
            output.append(f"🛠️ Option 1 (Aggressive): Buy a Put contract slightly In-The-Money (e.g., Strike ${round(highest_high)}).")
            output.append(f"🛠️ Option 2 (Income/Bullish Credit): Sell a Put out-of-the-money (e.g., Strike ${round(lowest_low)}) ONLY if you want to buy shares at support.")

        # Scenario C: Near Range Low -> Bullish/Neutral Setup
        elif recent_close <= (lowest_low + (avg_hourly_range * 2)):
            output.append("🎯 STRATEGY MATCH: SUPPORT BOUNCE PLAY")
            output.append("💡 Reason: Spot price is sitting at historic lows of the current range.")
            output.append(f"🛠️ Option: Sell-to-Open an Out-Of-The-Money (OTM) Put at or below ${round(lowest_low)} to collect premium (Credit Spread / Cash-Secured Put).")
        
        # Scenario D: Chop / Idle Range
        else:
            output.append("🎯 STRATEGY MATCH: RANGE CHOP (No Clean Direction)")
            output.append(f"💡 Reason: Price is floating in the middle of the ${lowest_low:.2f} - ${highest_high:.2f} range.")
            output.append("🛠️ Option: Wait for a breakout or look for an Iron Condor to capture decaying premium.")

        return "\n".join(output)

    except Exception as e:
        return f"Error executing strategy analyzer: {str(e)}"

@mcp.tool()
def get_option_chain(underlying_symbol: str, expiration_date_gte: str = None, expiration_date_lte: str = None, contract_type: str = None, limit: int = 20) -> str:
    """
    Fetches available option contracts for an underlying symbol (e.g., SPY, AAPL).
    contract_type can be 'call' or 'put'.
    Returns a formatted list of contract symbols, strike prices, expiration dates, and types.
    """
    try:
        url = f"{ENDPOINT}/options/contracts"
        params = {
            "underlying_symbols": underlying_symbol.upper(),
            "status": "active",
            "limit": min(limit, 100)
        }
        if expiration_date_gte:
            params["expiration_date_gte"] = expiration_date_gte
        if expiration_date_lte:
            params["expiration_date_lte"] = expiration_date_lte
        if contract_type:
            params["type"] = contract_type.lower()

        response = requests.get(url, params=params, headers=_auth_headers())
        if response.status_code != 200:
            return f"Failed to fetch option contracts: {response.text}"

        data = response.json()
        contracts = data.get("option_contracts", [])
        if not contracts:
            return f"No active option contracts found for {underlying_symbol.upper()}."

        lines = [f"=== 📜 OPTION CONTRACTS FOR {underlying_symbol.upper()} ==="]
        for c in contracts:
            sym = c.get("symbol")
            exp = c.get("expiration_date")
            strike = c.get("strike_price")
            ctype = c.get("type", "").upper()
            lines.append(f"• Contract: {sym} | Type: {ctype} | Strike: ${strike} | Expiration: {exp}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching option chain: {str(e)}"

@mcp.tool()
def execute_long_straddle(call_symbol: str, put_symbol: str, call_price: float, put_price: float, qty: int = 1) -> str:
    """
    Executes a Long Straddle by buying both an ATM Call and ATM Put option contract.
    Safely rolls back if one leg fails.
    """
    res = long_straddle(
        call_symbol=call_symbol,
        put_symbol=put_symbol,
        call_buy_price=call_price,
        put_buy_price=put_price,
        qty=qty
    )
    return json.dumps(res, indent=2)

@mcp.tool()
def execute_bull_call_spread(lower_call_symbol: str, higher_call_symbol: str, buy_price: float, sell_price: float, qty: int = 1) -> str:
    """
    Executes a Bull Call Spread (Debit Call Spread):
    Buys lower strike call, sells higher strike call.
    """
    res = bull_call_spread(
        lower_call_symbol=lower_call_symbol,
        higher_call_symbol=higher_call_symbol,
        buy_price=buy_price,
        sell_price=sell_price,
        qty=qty
    )
    return json.dumps(res, indent=2)

@mcp.tool()
def execute_bear_put_spread(higher_put_symbol: str, lower_put_symbol: str, buy_price: float, sell_price: float, qty: int = 1) -> str:
    """
    Executes a Bear Put Spread (Debit Put Spread):
    Buys higher strike put, sells lower strike put.
    """
    res = bear_put_spread(
        higher_put_symbol=higher_put_symbol,
        lower_put_symbol=lower_put_symbol,
        buy_price=buy_price,
        sell_price=sell_price,
        qty=qty
    )
    return json.dumps(res, indent=2)

@mcp.tool()
def execute_bull_put_spread(lower_put_symbol: str, higher_put_symbol: str, buy_price: float, sell_price: float, qty: int = 1) -> str:
    """
    Executes a Bull Put Spread (Credit Put Spread):
    Buys lower strike put (protection), sells higher strike put (income).
    """
    res = bull_put_spread(
        lower_put_symbol=lower_put_symbol,
        higher_put_symbol=higher_put_symbol,
        buy_price=buy_price,
        sell_price=sell_price,
        qty=qty
    )
    return json.dumps(res, indent=2)

@mcp.tool()
def execute_iron_condor(
    put_buy_symbol: str,
    put_sell_symbol: str,
    call_sell_symbol: str,
    call_buy_symbol: str,
    put_buy_price: float,
    put_sell_price: float,
    call_sell_price: float,
    call_buy_price: float,
    qty: int = 1
) -> str:
    """
    Executes an Iron Condor by placing both a Bull Put Spread and Bear Call Spread.
    Automatically rolls back open legs if any execution fails.
    """
    res = iron_condor(
        put_buy_symbol=put_buy_symbol,
        put_sell_symbol=put_sell_symbol,
        call_sell_symbol=call_sell_symbol,
        call_buy_symbol=call_buy_symbol,
        put_buy_price=put_buy_price,
        put_sell_price=put_sell_price,
        call_sell_price=call_sell_price,
        call_buy_price=call_buy_price,
        qty=qty
    )
    return json.dumps(res, indent=2)

@mcp.tool()
def get_open_positions() -> str:
    """
    Returns all current open positions and option legs with current quantities and unrealized profit/loss.
    """
    res = getPositions()
    if res.get("status") != "success":
        return f"Error retrieving positions: {res.get('reason')}"
    
    positions = res.get("positions", [])
    if not positions:
        return "No open positions found."

    lines = ["=== 💼 CURRENT OPEN POSITIONS ==="]
    for p in positions:
        sym = p.get("symbol")
        qty = p.get("qty")
        cost = p.get("avg_entry_price")
        curr = p.get("current_price")
        pl = p.get("unrealized_pl")
        plpc = p.get("unrealized_plpc")
        lines.append(f"• {sym}: Qty {qty} | Entry: ${cost} | Current: ${curr} | P/L: ${pl} ({float(plpc)*100:.2f}%)")

    return "\n".join(lines)

@mcp.tool()
def liquidate_position(symbol: str, percentage: int = 100) -> str:
    """
    Liquidates an open equity or option contract position by symbol.
    percentage defaults to 100%.
    """
    res = closeAPosition(symbol=symbol, percentage=percentage)
    return json.dumps(res, indent=2)

if __name__ == "__main__":
    if "--mcp" in sys.argv:
        sys.stderr.write("AlpacaOptionsDesk MCP Server is running and listening on stdio...\n")
        sys.stderr.flush()
        mcp.run(transport="stdio")
    else:
        from MVP_AI.ai_use import DeepSeekOptionsTrader
        ticker = "SPY"
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                ticker = arg
                break
        print(f"🚀 Launching DeepSeek Options Trading Engine for {ticker.upper()}...")
        trader = DeepSeekOptionsTrader()
        trader.run_cycle(symbol=ticker)



