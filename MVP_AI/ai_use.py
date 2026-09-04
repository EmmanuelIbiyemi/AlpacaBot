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

# This importing is for another agent to tell me the execution time and fill price it should do for me 
from execution_agent import OptionsExecutionAgent

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

        total_span = highest_high - lowest_low
        range_pos = round(((recent_close - lowest_low) / total_span * 100), 1) if total_span > 0 else 50.0

        if range_pos >= 80:
            tech_bias = "TESTING_RESISTANCE_NEAR_HIGHS"
        elif range_pos <= 20:
            tech_bias = "TESTING_SUPPORT_NEAR_LOWS"
        elif 35 <= range_pos <= 65 and not high_volatility:
            tech_bias = "MID_RANGE_CHOP_NEUTRAL"
        else:
            tech_bias = "DIRECTIONAL_MOMENTUM"

        return {
            "symbol": symbol,
            "current_spot_price": round(recent_close, 2),
            "recent_high": round(highest_high, 2),
            "recent_low": round(lowest_low, 2),
            "range_position_pct": range_pos,
            "technical_setup": tech_bias,
            "avg_hourly_range": round(avg_hourly_range, 2),
            "recent_hourly_range": round(recent_hourly_range, 2),
            "is_high_volatility": high_volatility
        }


    def fetch_option_contracts(self, symbol: str, spot_price: float = None, limit_per_type: int = 10) -> list:
        """
        Fetches active call and put contracts from Alpaca near current date and spot price.
        Ensures a balanced set of both Calls and Puts so spreads and iron condors can execute.
        """
        url = f"{ENDPOINT}/options/contracts"
        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")
        max_exp = (today + timedelta(days=60)).strftime("%Y-%m-%d")

        base_params = {
            "underlying_symbols": symbol.upper(),
            "status": "active",
            "expiration_date_gte": today_str,
            "expiration_date_lte": max_exp,
            "limit": limit_per_type
        }

        if spot_price and spot_price > 0:
            base_params["strike_price_gte"] = str(round(spot_price * 0.92, 2))
            base_params["strike_price_lte"] = str(round(spot_price * 1.08, 2))

        # 1. Fetch Calls
        call_params = dict(base_params)
        call_params["type"] = "call"
        call_resp = requests.get(url, params=call_params, headers=self.alpaca_headers)
        call_contracts = call_resp.json().get("option_contracts", []) if call_resp.status_code == 200 else []

        # 2. Fetch Puts
        put_params = dict(base_params)
        put_params["type"] = "put"
        put_resp = requests.get(url, params=put_params, headers=self.alpaca_headers)
        put_contracts = put_resp.json().get("option_contracts", []) if put_resp.status_code == 200 else []

        contracts = call_contracts + put_contracts

        # Fallback if strike filter returned empty
        if not contracts:
            fallback_params = {
                "underlying_symbols": symbol.upper(),
                "status": "active",
                "expiration_date_gte": today_str,
                "limit": limit_per_type * 2
            }
            fb_resp = requests.get(url, params=fallback_params, headers=self.alpaca_headers)
            if fb_resp.status_code == 200:
                contracts = fb_resp.json().get("option_contracts", [])

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
            "You are a Senior Quantitative Options Trader.\n"
            "Analyze technical structure, location in 5-day range (range_position_pct), and volatility to pick the right strategy:\n\n"
            "MANDATORY STRATEGY RULES:\n"
            "1. TESTING_RESISTANCE_NEAR_HIGHS (range_position_pct >= 80%):\n"
            "   - Preferred Strategy: BEAR_PUT_SPREAD (Debit Put Spread) or BEAR_CALL_SPREAD.\n"
            "   - Why: Overextended near resistance limits. High probability of pullback.\n"
            "   - FORBIDDEN: DO NOT use Iron Condor near the ceiling (an upward breach causes max loss on call wing).\n\n"
            "2. TESTING_SUPPORT_NEAR_LOWS (range_position_pct <= 20%):\n"
            "   - Preferred Strategy: BULL_CALL_SPREAD (Debit Call Spread) or BULL_PUT_SPREAD.\n"
            "   - Why: Sitting at major support. High probability of bounce.\n"
            "   - FORBIDDEN: DO NOT use Iron Condor near the floor (a downward breach causes max loss on put wing).\n\n"
            "3. MID_RANGE_CHOP_NEUTRAL (range_position_pct between 35% and 65% with low volatility):\n"
            "   - Preferred Strategy: IRON_CONDOR (Sell OTM Put Spread + Sell OTM Call Spread).\n"
            "   - Why: Price is balanced away from both wings, ideal for theta decay.\n"
            "   - FORBIDDEN: DO NOT use Long Straddle in chop (theta burn).\n\n"
            "4. HIGH_VOLATILITY_BREAKOUT (Hourly range expanding rapidly, breakout past 5-day high/low):\n"
            "   - Preferred Strategy: LONG_STRADDLE (Buy ATM Call + Buy ATM Put).\n"
            "   - Why: Explosive move expected in either direction.\n\n"
            "EXECUTION & FORMAT RULES:\n"
            "- Keep market_summary and reasoning concise (max 2 sentences each). DO NOT output giant text blocks.\n"
            "- If bid/ask prices are null, estimate reasonable limit prices ($1.00 - $3.00) and execute.\n"
            "- Select real contract symbols from available_option_contracts.\n"
            "- Set trade_action.execute = true when an actionable setup is detected.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "market_regime": "BEARISH_RESISTANCE" | "BULLISH_SUPPORT" | "MID_RANGE_CHOP" | "VOLATILITY_BREAKOUT",\n'
            '  "strategy": "BEAR_PUT_SPREAD" | "BULL_CALL_SPREAD" | "BULL_PUT_SPREAD" | "IRON_CONDOR" | "LONG_STRADDLE" | "HOLD",\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "strategy_suitability": "Why this strategy is ideal and why competing ones fail here",\n'
            '  "market_summary": "1-2 sentence overview",\n'
            '  "reasoning": "1-2 sentence technical justification",\n'
            '  "trade_action": {\n'
            '    "execute": true | false,\n'
            '    "strategy_name": "bear_put_spread" | "bull_call_spread" | "bull_put_spread" | "iron_condor" | "long_straddle",\n'
            '    "parameters": {\n'
            '      "call_symbol": "OCC symbol",\n'
            '      "put_symbol": "OCC symbol",\n'
            '      "lower_call_symbol": "OCC symbol",\n'
            '      "higher_call_symbol": "OCC symbol",\n'
            '      "higher_put_symbol": "OCC symbol",\n'
            '      "lower_put_symbol": "OCC symbol",\n'
            '      "put_buy_symbol": "for iron condor",\n'
            '      "put_sell_symbol": "for iron condor",\n'
            '      "call_sell_symbol": "for iron condor",\n'
            '      "call_buy_symbol": "for iron condor",\n'
            '      "call_price": 1.50,\n'
            '      "put_price": 1.50,\n'
            '      "buy_price": 1.50,\n'
            '      "sell_price": 0.50,\n'
            '      "put_buy_price": 0.50,\n'
            '      "put_sell_price": 1.50,\n'
            '      "call_sell_price": 1.50,\n'
            '      "call_buy_price": 0.50,\n'
            '      "qty": 1\n'
            "    }\n"
            "  }\n"
            "}"
        )

        user_content = json.dumps({
            "market_snapshot": market_snapshot,
            "available_option_contracts": options_candidates[:20],
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
            "temperature": 0.2,
            "max_tokens": 1500
        }

        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek API error {response.status_code}: {response.text}")

        res_json = response.json()
        raw_text = res_json["choices"][0]["message"]["content"].strip()

        # Clean markdown codeblocks if returned
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        import re
        try:
            return json.loads(raw_text)
        except Exception:
            # Fallback regex search for JSON
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Could not parse DeepSeek JSON response: {raw_text[:200]}...")



    def execute_deepseek_trade(self, decision: dict) -> dict:
        """
        Executes the strategy decided by DeepSeek on Alpaca Paper Trading.
        """
        trade_action = decision.get("trade_action", {})
        if not trade_action.get("execute", False):
            return {"status": "skipped", "message": "DeepSeek recommended HOLD or no execution"}

        strat = trade_action.get("strategy_name", "").lower().replace("-", "_")
        params = trade_action.get("parameters", {})
        qty = int(params.get("qty", 1))

        if "straddle" in strat:
            call_sym = params.get("call_symbol") or params.get("call_leg") or params.get("call")
            put_sym = params.get("put_symbol") or params.get("put_leg") or params.get("put")
            call_p = float(params.get("call_price") or params.get("call_buy_price") or 1.0)
            put_p = float(params.get("put_price") or params.get("put_buy_price") or 1.0)
            print(f"⚡ Submitting Long Straddle: Call {call_sym} @ ${call_p} | Put {put_sym} @ ${put_p} | Qty {qty}")
            return long_straddle(
                call_symbol=call_sym,
                put_symbol=put_sym,
                call_buy_price=call_p,
                put_buy_price=put_p,
                qty=qty
            )
        elif "bull_call" in strat:
            lower_call = params.get("lower_call_symbol") or params.get("buy_symbol") or params.get("call_buy")
            higher_call = params.get("higher_call_symbol") or params.get("sell_symbol") or params.get("call_sell")
            buy_p = float(params.get("buy_price") or params.get("call_buy_price") or 1.0)
            sell_p = float(params.get("sell_price") or params.get("call_sell_price") or 0.5)
            print(f"⚡ Submitting Bull Call Spread: Buy {lower_call} @ ${buy_p} | Sell {higher_call} @ ${sell_p} | Qty {qty}")
            return bull_call_spread(
                lower_call_symbol=lower_call,
                higher_call_symbol=higher_call,
                buy_price=buy_p,
                sell_price=sell_p,
                qty=qty
            )
        elif "bear_put" in strat:
            higher_put = params.get("higher_put_symbol") or params.get("buy_symbol") or params.get("put_buy")
            lower_put = params.get("lower_put_symbol") or params.get("sell_symbol") or params.get("put_sell")
            buy_p = float(params.get("buy_price") or params.get("put_buy_price") or 1.0)
            sell_p = float(params.get("sell_price") or params.get("put_sell_price") or 0.5)
            print(f"⚡ Submitting Bear Put Spread: Buy {higher_put} @ ${buy_p} | Sell {lower_put} @ ${sell_p} | Qty {qty}")
            return bear_put_spread(
                higher_put_symbol=higher_put,
                lower_put_symbol=lower_put,
                buy_price=buy_p,
                sell_price=sell_p,
                qty=qty
            )
        elif "bull_put" in strat:
            lower_put = params.get("lower_put_symbol") or params.get("buy_symbol") or params.get("put_buy")
            higher_put = params.get("higher_put_symbol") or params.get("sell_symbol") or params.get("put_sell")
            buy_p = float(params.get("buy_price") or 0.5)
            sell_p = float(params.get("sell_price") or 1.0)
            print(f"⚡ Submitting Bull Put Spread: Buy {lower_put} @ ${buy_p} | Sell {higher_put} @ ${sell_p} | Qty {qty}")
            return bull_put_spread(
                lower_put_symbol=lower_put,
                higher_put_symbol=higher_put,
                buy_price=buy_p,
                sell_price=sell_p,
                qty=qty
            )
        elif "iron_condor" in strat:
            put_buy = params.get("put_buy_symbol") or params.get("lower_put_symbol") or params.get("put_buy") or params.get("long_put")
            put_sell = params.get("put_sell_symbol") or params.get("higher_put_symbol") or params.get("put_sell") or params.get("short_put")
            call_sell = params.get("call_sell_symbol") or params.get("lower_call_symbol") or params.get("call_sell") or params.get("short_call")
            call_buy = params.get("call_buy_symbol") or params.get("higher_call_symbol") or params.get("call_buy") or params.get("long_call")

            return iron_condor(
                put_buy_symbol=put_buy,
                put_sell_symbol=put_sell,
                call_sell_symbol=call_sell,
                call_buy_symbol=call_buy,
                put_buy_price=float(params.get("put_buy_price", 0.5)),
                put_sell_price=float(params.get("put_sell_price", 1.0)),
                call_sell_price=float(params.get("call_sell_price", 1.0)),
                call_buy_price=float(params.get("call_buy_price", 0.5)),
                qty=qty,
                limit_price=float(params.get("limit_price", 1.0))
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
        print(f"📊 Range: ${snapshot['recent_low']} - ${snapshot['recent_high']} (At {snapshot['range_position_pct']}% of range)")
        print(f"📍 Technical Setup: {snapshot['technical_setup']}")
        print(f"⚡ High Volatility: {snapshot['is_high_volatility']}")


        # 2. Fetch Options Candidates (filtered around current spot price)
        contracts = self.fetch_option_contracts(symbol, spot_price=snapshot['current_spot_price'])
        print(f"📜 Available Option Contracts Retrieved: {len(contracts)}")


        # 3. Fetch Open Positions
        pos_resp = getPositions()
        open_positions = pos_resp.get("positions", []) if pos_resp.get("status") == "success" else []
        print(f"💼 Current Open Positions: {len(open_positions)}")

        # 4. Ask DeepSeek
        print(f"\n🧠 Consulting DeepSeek AI for strategic decision...")
        decision = self.ask_deepseek(snapshot, contracts, open_positions)

        print(f"\n💡 DeepSeek Decision:")
        print(f"   • Market Regime: {decision.get('market_regime')}")
        print(f"   • Recommended Strategy: {decision.get('strategy')}")
        print(f"   • Confidence: {decision.get('confidence')}")
        print(f"   • Strategy Suitability: {decision.get('strategy_suitability')}")
        print(f"   • Market Summary: {decision.get('market_summary')}")
        print(f"   • Technical Reasoning: {decision.get('reasoning')}")


        # 5. Execute
        # This is to add the execution fill type
        execution_result = self.execute_deepseek_trade(decision)
        execution_filltype_ = OptionsExecutionAgent.calculate_fill_price(decision.get('strategy'), decision.get('params'), snapshot.get('current_spot_price'))
        print(f" Exeution price : response {execution_filltype_}")
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

DEFAULT_WATCHLIST = [
    "SPY",   # S&P 500 ETF (Most liquid options market)
    "QQQ",   # Nasdaq 100 ETF (Tech heavy volatility)
    "TSLA",  # Tesla (High implied volatility)
    "NVDA",  # Nvidia (High volume AI leader)
    "AAPL",  # Apple (Mega-cap tech)
    "AMD",   # Advanced Micro Devices (High beta semi)
    "AMZN",  # Amazon (E-commerce / AWS)
    "META",  # Meta Platforms (Social media / AI)
    "MSFT",  # Microsoft (Enterprise / Cloud)
    "GOOGL"  # Alphabet (Search / AI)
]

if __name__ == "__main__":
    trader = DeepSeekOptionsTrader()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        targets = [sys.argv[1].upper()]
    else:
        targets = DEFAULT_WATCHLIST

    print(f"🚀 Launching DeepSeek Options Scanner on {len(targets)} stock(s): {', '.join(targets)}\n")
    for t in targets:
        try:
            trader.run_cycle(symbol=t)
        except Exception as e:
            print(f"❌ Error analyzing {t}: {e}\n")

