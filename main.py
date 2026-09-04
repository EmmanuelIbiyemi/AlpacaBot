

# # This is where the main bot will trigger everything when the bot have meet it's requirements
# # or when the bot detects that it's time to buy or sell

# def order_botTrigger():
#     try:


#         return {
#             "status":"success",
#             "result":"" 
#         }

#     except Exception as e: 
#         return {
#             "status":"error",
#             "reason":str(e)
#         }

# def position_botTrigger():
#     try:


#         return {
#             "status":"success",
#             "result":"" 
#         }

#     except Exception as e: 
#         return {
#             "status":"error",
#             "reason":str(e)
#         }


import os
from datetime import datetime, timedelta, timezone
import pandas as pd
from mcp.server.fastmcp import FastMCP

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# URLS AND KEYS
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT, APIKEY, APISECRET

mcp = FastMCP("AlpacaOptionsDesk")

# Initialize Alpaca Clients
API_KEY = APIKEY
SECRET_KEY = APISECRET
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

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

if __name__ == "__main__":
    mcp.run(transport="stdio")
