import os
import sys
import json
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT, APIKEY, APISECRET, DEEPSEEK_API_KEY
from funcs.charts.charts import get_latest_option_quotes, get_option_bars

from funcs.straddles.straddles import (
    long_straddle,
    bull_call_spread,
    bear_put_spread,
    bull_put_spread,
    iron_condor
)
from funcs.positions.position import getPositions, closeAPosition

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DATA_BASE_URL = "https://data.alpaca.markets"

class DeepSeekOptionsTrader:
    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEP_SEEK_API_KEY is not set in your .env file!")
        
        self.api_key = DEEPSEEK_API_KEY
        self.alpaca_headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": APIKEY,
            "APCA-API-SECRET-KEY": APISECRET
        }

    def fetch_market_data(self, symbol: str, lookback_days: int = 5) -> dict:
        """
        Gathers hourly candle metrics, ranges, and volatility for the symbol using Alpaca REST API.
        """
        symbol = symbol.upper()
        end_time = datetime.now(timezone.utc) - timedelta(minutes=16) 
        start_time = end_time - timedelta(days=lookback_days)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{DATA_BASE_URL}/v2/stocks/{symbol}/bars?timeframe=1Hour&start={start_str}&end={end_str}&limit=100"
        resp = requests.get(url, headers=self.alpaca_headers)

        if resp.status_code != 200:
            raise ValueError(f"Failed to fetch market data from Alpaca: {resp.text}")

        data = resp.json()
        bars = data.get("bars", [])
        if not bars:
            raise ValueError(f"No chart bars available for {symbol}")

        df = pd.DataFrame(bars)
        recent_close = float(df['c'].iloc[-1])
        highest_high = float(df['h'].max())
        lowest_low = float(df['l'].min())
        df['hourly_range'] = df['h'] - df['l']
        avg_hourly_range = float(df['hourly_range'].mean())
        recent_hourly_range = float(df['hourly_range'].iloc[-5:].mean())
        high_volatility = bool(recent_hourly_range > (avg_hourly_range * 1.2))

        return {
            "symbol": symbol,
            "current_spot_price": round(recent_close, 2),
            "recent_high": round(highest_high, 2),
            "recent_low": round(lowest_low, 2),
            "avg_hourly_range": round(avg_hourly_range, 2),
            "recent_hourly_range": round(recent_hourly_range, 2),
            "is_high_volatility": high_volatility
        }


    def fetch_option_contracts(self, symbol: str, limit: int = 30) -> list:
        """
        Fetches active call and put contracts from Alpaca near current date.
        """
        url = f"{ENDPOINT}/options/contracts"
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        params = {
            "underlying_symbols": symbol.upper(),
            "status": "active",
            "expiration_date_gte": today_str,
            "limit": limit
        }
        resp = requests.get(url, params=params, headers=self.alpaca_headers)
        if resp.status_code != 200:
            return []

        contracts = resp.json().get("option_contracts", [])
        contract_symbols = [c.get("symbol") for c in contracts if c.get("symbol")]
        
        quotes_data = {}
        if contract_symbols:
            quotes_res = get_latest_option_quotes(contract_symbols[:20])
            if quotes_res.get("status") == "success":
                quotes_data = quotes_res.get("data", {}).get("quotes", {})

        return [
            {
                "symbol": c.get("symbol"),
                "type": c.get("type"),
                "strike_price": float(c.get("strike_price")),
                "expiration_date": c.get("expiration_date"),
                "bid": quotes_data.get(c.get("symbol"), {}).get("bp"),
                "ask": quotes_data.get(c.get("symbol"), {}).get("ap")
            }
            for c in contracts
        ]


    def ask_deepseek(self, market_snapshot: dict, options_candidates: list, open_positions: list) -> dict:
        """
        Sends the market context and option chain to DeepSeek AI to decide which strategy to trade.
        """
        system_prompt = (
            "You are a professional quantitative options trading intelligence bot. "
            "You analyze stock market technical structure, volatility, and option chains. "
            "You choose among the following strategies based on market regime:\n"
            "- LONG_STRADDLE (High volatility, imminent breakout, ATM Call + ATM Put)\n"
            "- BULL_CALL_SPREAD (Bullish momentum, buy lower call, sell higher call)\n"
            "- BEAR_PUT_SPREAD (Bearish resistance rejection, buy higher put, sell lower put)\n"
            "- BULL_PUT_SPREAD (Bullish/neutral support bounce, credit put spread)\n"
            "- IRON_CONDOR (Range-bound chop, sell OTM put spread + sell OTM call spread)\n"
            "- HOLD (Uncertain market, no high-probability setup)\n\n"
            "CRITICAL: Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "market_summary": "1-2 sentence overview of volatility and price action",\n'
            '  "strategy": "LONG_STRADDLE" | "BULL_CALL_SPREAD" | "BEAR_PUT_SPREAD" | "BULL_PUT_SPREAD" | "IRON_CONDOR" | "HOLD",\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "reasoning": "Detailed justification",\n'
            '  "trade_action": {\n'
            '    "execute": true | false,\n'
            '    "strategy_name": "long_straddle" | "bull_call_spread" | "bear_put_spread" | "bull_put_spread" | "iron_condor",\n'
            '    "parameters": {\n'
            '      "call_symbol": "...",\n'
            '      "put_symbol": "...",\n'
            '      "call_price": 1.50,\n'
            '      "put_price": 1.50,\n'
            '      "qty": 1\n'
            "    }\n"
            "  }\n"
            "}"
        )

        user_content = json.dumps({
            "market_snapshot": market_snapshot,
            "available_option_contracts": options_candidates[:25],
            "current_portfolio_positions": open_positions
        }, indent=2)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this market data and make a trade decision:\n{user_content}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek API error {response.status_code}: {response.text}")

        res_json = response.json()
        raw_text = res_json["choices"][0]["message"]["content"]
        return json.loads(raw_text)

    def execute_deepseek_trade(self, decision: dict) -> dict:
        """
        Executes the strategy decided by DeepSeek.
        """
        trade_action = decision.get("trade_action", {})
        if not trade_action.get("execute", False):
            return {"status": "skipped", "message": "DeepSeek recommended HOLD or no execution"}

        strat = trade_action.get("strategy_name", "").lower()
        params = trade_action.get("parameters", {})
        qty = int(params.get("qty", 1))

        if strat == "long_straddle":
            return long_straddle(
                call_symbol=params.get("call_symbol"),
                put_symbol=params.get("put_symbol"),
                call_buy_price=float(params.get("call_price", 1.0)),
                put_buy_price=float(params.get("put_price", 1.0)),
                qty=qty
            )
        elif strat == "bull_call_spread":
            return bull_call_spread(
                lower_call_symbol=params.get("lower_call_symbol"),
                higher_call_symbol=params.get("higher_call_symbol"),
                buy_price=float(params.get("buy_price", 1.0)),
                sell_price=float(params.get("sell_price", 0.5)),
                qty=qty
            )
        elif strat == "bear_put_spread":
            return bear_put_spread(
                higher_put_symbol=params.get("higher_put_symbol"),
                lower_put_symbol=params.get("lower_put_symbol"),
                buy_price=float(params.get("buy_price", 1.0)),
                sell_price=float(params.get("sell_price", 0.5)),
                qty=qty
            )
        elif strat == "bull_put_spread":
            return bull_put_spread(
                lower_put_symbol=params.get("lower_put_symbol"),
                higher_put_symbol=params.get("higher_put_symbol"),
                buy_price=float(params.get("buy_price", 0.5)),
                sell_price=float(params.get("sell_price", 1.0)),
                qty=qty
            )
        elif strat == "iron_condor":
            return iron_condor(
                put_buy_symbol=params.get("put_buy_symbol"),
                put_sell_symbol=params.get("put_sell_symbol"),
                call_sell_symbol=params.get("call_sell_symbol"),
                call_buy_symbol=params.get("call_buy_symbol"),
                put_buy_price=float(params.get("put_buy_price", 0.5)),
                put_sell_price=float(params.get("put_sell_price", 1.0)),
                call_sell_price=float(params.get("call_sell_price", 1.0)),
                call_buy_price=float(params.get("call_buy_price", 0.5)),
                qty=qty
            )
        else:
            return {"status": "error", "reason": f"Unknown strategy: {strat}"}

    def run_cycle(self, symbol: str = "SPY") -> dict:
        """
        Full autonomous pipeline:
        1. Read market data from Alpaca
        2. Query option contracts
        3. Consult DeepSeek AI
        4. Execute trade if recommended
        """
        print(f"\n==========================================")
        print(f"🤖 DEEPSEEK OPTIONS BOT: Analyzing {symbol.upper()}")
        print(f"==========================================")

        # 1. Fetch Market Context
        snapshot = self.fetch_market_data(symbol)
        print(f"📈 Spot Price: ${snapshot['current_spot_price']}")
        print(f"📊 Range: ${snapshot['recent_low']} - ${snapshot['recent_high']}")
        print(f"⚡ High Volatility: {snapshot['is_high_volatility']}")

        # 2. Fetch Options Candidates
        contracts = self.fetch_option_contracts(symbol)
        print(f"📜 Available Option Contracts Retrieved: {len(contracts)}")

        # 3. Fetch Open Positions
        pos_resp = getPositions()
        open_positions = pos_resp.get("positions", []) if pos_resp.get("status") == "success" else []
        print(f"💼 Current Open Positions: {len(open_positions)}")

        # 4. Ask DeepSeek
        print(f"\n🧠 Consulting DeepSeek AI for strategic decision...")
        decision = self.ask_deepseek(snapshot, contracts, open_positions)

        print(f"\n💡 DeepSeek Decision:")
        print(f"   • Strategy: {decision.get('strategy')}")
        print(f"   • Confidence: {decision.get('confidence')}")
        print(f"   • Summary: {decision.get('market_summary')}")
        print(f"   • Reasoning: {decision.get('reasoning')}")

        # 5. Execute
        execution_result = self.execute_deepseek_trade(decision)
        print(f"\n🚀 Execution Result: {execution_result.get('status')}")
        if execution_result.get("status") == "success":
            print(f"   ✅ Strategy '{decision.get('strategy')}' executed successfully on Alpaca Paper Trading!")
        elif execution_result.get("status") == "skipped":
            print(f"   ⏸️ {execution_result.get('message')}")
        else:
            print(f"   ⚠️ Reason: {execution_result.get('reason')}")

        return {
            "snapshot": snapshot,
            "decision": decision,
            "execution": execution_result
        }

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    trader = DeepSeekOptionsTrader()
    trader.run_cycle(symbol=ticker)
