import os
import sys
import json
import re
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from urls.urls import DEEPSEEK_API_KEY

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

EXECUTION_AGENT_SYSTEM_PROMPT = """You are an expert Options Execution Agent specializing in Alpaca's API framework. Your primary objective is to calculate optimal, highly fillable multi-leg option limit prices and track order execution status.

When given an Iron Condor or multi-leg strategy, perform the following tasks:

1. UNDERSTAND THE ALPACA FILL RULE:
   - Alpaca requires Net Credit orders (e.g., Iron Condor, Bull Put Spread, Bear Call Spread) to be submitted as a NEGATIVE limit price string (e.g., "-1.00", "-0.95").
   - Alpaca requires Net Debit orders (e.g., Long Straddle, Bull Call Spread, Bear Put Spread) to be submitted as a POSITIVE limit price string (e.g., "1.50", "2.10").

2. CALCULATE THE FILLING PRICE:
   - Identify the Midpoint Price of the options spread: (Bid + Ask) / 2 for each leg or net spread.
   - For an immediate "quick fill" (Market-able Limit Order), shave off a slight discount (approx $0.05 to $0.10) from the midpoint.
   - If the Midpoint is a $1.09 Credit, instruct the user to use a Limit Price of "-1.00" or "-0.95" to ensure the order fills immediately.
   - If bid/ask is null or zero (e.g., off-hours paper trading), estimate a realistic midpoint (e.g., $1.00 - $2.50) and apply the rule.

3. PROVIDE THE OUTPUT FORMAT:
   - Always state the exact current Midpoint Price.
   - Always output the precise 'limit_price' string to pass to the Alpaca API payload (MUST BE NEGATIVE for credits, POSITIVE for debits).
   - Explain what the order status tracking should look like (e.g., checking if 'status' == 'filled').

Respond ONLY with a valid JSON object matching this schema:
{
  "strategy_type": "NET_CREDIT" | "NET_DEBIT",
  "midpoint_price": 1.09,
  "limit_price": "-0.95",
  "explanation": "Calculated net credit midpoint $1.09. Shaved $0.14 discount for marketable fill on Alpaca as negative limit price string.",
  "status_tracking_guidance": "Order will enter 'accepted' or 'new' status, and transition to 'filled' once liquidity matches."
}
"""

class OptionsExecutionAgent:
    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEP_SEEK_API_KEY is not set in your .env file!")
        self.api_key = DEEPSEEK_API_KEY

    def calculate_fill_price(self, strategy_name: str, parameters: dict, contract_quotes: list) -> dict:
        """
        Consults the Options Execution Agent to determine the optimal fillable limit price according to Alpaca rules.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        user_content = json.dumps({
            "selected_strategy": strategy_name,
            "order_parameters": parameters,
            "relevant_contract_quotes": contract_quotes
        }, indent=2)

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": EXECUTION_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Calculate the optimal Alpaca limit price and fill instructions for this order:\n{user_content}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1000
        }

        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Execution Agent API error {response.status_code}: {response.text}")

        res_json = response.json()
        raw_text = res_json["choices"][0]["message"]["content"].strip()

        # Clean markdown wrappers if any
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            return json.loads(raw_text)
        except Exception:
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Could not parse Execution Agent response: {raw_text[:200]}")
