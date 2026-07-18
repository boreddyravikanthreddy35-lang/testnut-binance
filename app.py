"""
Flask Web Application for Binance Futures Testnet Trading Bot.
Provides a full browser-based UI to place orders, check balance, and stream logs.
"""

from __future__ import annotations

import json
import os
import sys
import time
import queue
import threading

from flask import Flask, render_template, request, jsonify, Response, stream_with_context

# Make sure bot package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot.logging_config import setup_logging, get_logger
from bot.validators import validate_all, ValidationError
from bot.client import BinanceClient, BinanceAPIError
from bot.orders import OrderManager

app = Flask(__name__)
setup_logging(level="DEBUG")
logger = get_logger(__name__)

# ── In-memory order history for this session ──────────────────────────────────
order_history: list[dict] = []

# ── SSE log queue ──────────────────────────────────────────────────────────────
log_queue: queue.Queue = queue.Queue(maxsize=200)


def _make_client(api_key: str, api_secret: str) -> BinanceClient:
    return BinanceClient(api_key=api_key, api_secret=api_secret)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/balance", methods=["POST"])
def get_balance():
    data = request.get_json()
    api_key    = (data.get("api_key") or "").strip()
    api_secret = (data.get("api_secret") or "").strip()

    if not api_key or not api_secret:
        return jsonify({"success": False, "error": "API Key and Secret are required."}), 400

    try:
        client = _make_client(api_key, api_secret)
        assets = client.get_account_info()
        result = [
            {
                "asset": a["asset"],
                "balance": float(a.get("balance", 0)),
                "available": float(a.get("availableBalance", 0)),
            }
            for a in assets
            if float(a.get("balance", 0)) > 0 or float(a.get("availableBalance", 0)) > 0
        ]
        logger.info("Balance fetched: %d assets", len(result))
        return jsonify({"success": True, "assets": result})
    except BinanceAPIError as e:
        logger.error("Balance API error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Balance unexpected error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": f"Network or unexpected error: {e}"}), 500


@app.route("/api/place_order", methods=["POST"])
def place_order():
    data = request.get_json()
    api_key    = (data.get("api_key") or "").strip()
    api_secret = (data.get("api_secret") or "").strip()
    symbol     = data.get("symbol", "")
    side       = data.get("side", "")
    order_type = data.get("order_type", "")
    quantity   = data.get("quantity", "")
    price      = data.get("price") or None
    tif        = data.get("time_in_force", "GTC")

    if not api_key or not api_secret:
        return jsonify({"success": False, "error": "API Key and Secret are required."}), 400

    # Validate inputs
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        client  = _make_client(api_key, api_secret)
        manager = OrderManager(client)
        ot = params["order_type"]

        if ot == "MARKET":
            result = manager.place_market_order(
                symbol=params["symbol"],
                side=params["side"],
                quantity=params["quantity"],
            )
        elif ot == "LIMIT":
            result = manager.place_limit_order(
                symbol=params["symbol"],
                side=params["side"],
                quantity=params["quantity"],
                price=params["price"],
                time_in_force=tif,
            )
        elif ot == "LIMIT_IOC":
            result = manager.place_limit_ioc_order(
                symbol=params["symbol"],
                side=params["side"],
                quantity=params["quantity"],
                price=params["price"],
            )
        else:
            return jsonify({"success": False, "error": f"Unknown order type: {ot}"}), 400

        response_data = {
            "success": result.success,
            "order_id": result.order_id,
            "client_order_id": result.client_order_id,
            "symbol": result.symbol,
            "side": result.side,
            "order_type": result.order_type,
            "status": result.status,
            "price": result.price,
            "avg_price": result.avg_price,
            "orig_qty": result.orig_qty,
            "executed_qty": result.executed_qty,
            "time_in_force": result.time_in_force,
            "error": result.error_message,
        }

        if result.success:
            order_history.insert(0, {
                **response_data,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            # Keep last 50
            if len(order_history) > 50:
                order_history.pop()

        return jsonify(response_data)

    except BinanceAPIError as e:
        logger.error("Order API error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Order unexpected error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


@app.route("/api/orders", methods=["GET"])
def get_orders():
    return jsonify({"orders": order_history})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Return last N lines from the log file."""
    log_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "logs", "trading_bot.log"
    )
    lines = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-100:]
    return jsonify({"logs": [l.rstrip() for l in lines]})


# ── AI Bot Brain ──────────────────────────────────────────────────────────────

import re
import random

BOT_KNOWLEDGE = {
    "greet":      ["hello","hi","hey","good morning","good afternoon","yo","sup","howdy"],
    "help":       ["help","what can you do","commands","features","capabilities","guide"],
    "market":     ["market order","market buy","market sell","what is market","market type"],
    "limit":      ["limit order","limit buy","limit sell","what is limit","limit price","gtc","ioc"],
    "ioc":        ["ioc","immediate or cancel","limit_ioc","fill or cancel"],
    "balance":    ["balance","funds","usdt","wallet","account","how much","money","assets"],
    "place":      ["place order","how to buy","how to sell","buy btc","sell btc","trade"],
    "symbol":     ["symbol","btcusdt","ethusdt","trading pair","which coin","what coin"],
    "log":        ["log","logs","logging","history","what happened","activity"],
    "error":      ["error","failed","problem","issue","not working","wrong","api error"],
    "keys":       ["api key","api keys","secret","credentials","authenticate","testnet key"],
    "testnet":    ["testnet","test net","fake money","virtual","simulated","test account"],
    "price":      ["price","current price","btc price","eth price","how much btc","market price"],
    "status":     ["status","order status","filled","new","pending","what is new","what is filled"],
    "quantity":   ["quantity","how many","amount","lot size","minimum","0.001"],
    "profit":     ["profit","pnl","gain","loss","performance","return","how am i doing"],
    "strategy":   ["strategy","best strategy","scalp","swing","trade idea","recommendation"],
    "thankyou":   ["thank","thanks","thank you","great","awesome","nice","good job","perfect"],
    "bye":        ["bye","goodbye","exit","quit","see you","cya"],
}

BOT_REPLIES = {
    "greet": [
        "Hey! I'm CryptoBot AI. I can help you place orders, check balances, explain order types, and guide you through the bot. What would you like to do?",
        "Hello, trader! Ready to make some testnet gains? Ask me anything about orders, balances, or how to use this bot.",
        "Hi there! I'm your AI trading assistant. Ask me about MARKET orders, LIMIT orders, balances, or anything else!",
    ],
    "help": [
        """Here's what I can help you with:

**Orders** — Place MARKET, LIMIT, or LIMIT_IOC orders
**Balance** — Check your USDT, BTC, USDC balances
**Explain** — What is a market order? What is IOC?
**Guide** — How to set up API keys, how to place your first trade
**Logs** — Understand what's in the activity logs
**Strategy** — Basic trading ideas and tips

Just ask me anything! e.g. "How do I place a limit order?" """,
    ],
    "market": [
        """**MARKET ORDER** — Executes immediately at the best available price.

- **Best for:** Quick entries/exits when price doesn't matter much
- **Pros:** Always fills instantly
- **Cons:** You don't control the exact price (slippage possible)
- **How to use:** Go to Place Order → select MARKET → enter quantity → click Place Order

Example CLI:
`python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001`""",
    ],
    "limit": [
        """**LIMIT ORDER** — Rests on the order book until price reaches your target.

- **Best for:** Precise entries when you want a specific price
- **TIF GTC:** Good-Till-Cancel — stays open until filled or cancelled
- **TIF IOC:** Immediate-Or-Cancel — fills what it can, cancels the rest
- **Requires:** Both quantity AND price

Example CLI:
`python cli.py --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 50000`""",
    ],
    "ioc": [
        """**LIMIT_IOC (Immediate-Or-Cancel)**

This is the bonus 3rd order type in this bot.

- Tries to fill at your limit price RIGHT NOW
- Whatever can't fill immediately is CANCELLED automatically
- Great for aggressive entries without leaving a resting order
- Will NOT sit on the order book

Example CLI:
`python cli.py --symbol BTCUSDT --side BUY --type LIMIT_IOC --quantity 0.001 --price 50000`""",
    ],
    "balance": [
        "Your testnet account has **5,000 USDT**, **5,000 USDC**, and **0.01 BTC**. Go to Dashboard → Balances or click 'Refresh' to see live numbers. Make sure your API keys are saved in Settings first!",
        "To check your balance, go to **Dashboard** and click **Refresh**, or use the CLI: `python cli.py --check-balance`. Your testnet starts with 5,000 USDT — no real money!",
    ],
    "place": [
        """To place an order:

1. Go to **Settings** → enter your API Key & Secret → Save & Connect
2. Go to **Place Order** tab
3. Select order type: MARKET / LIMIT / LIMIT_IOC
4. Choose BUY or SELL
5. Enter Symbol (e.g. BTCUSDT) and Quantity (e.g. 0.001)
6. For LIMIT: enter a price too
7. Click **Place Order** — result appears on the right!

Or use the **Quick Order** buttons on Dashboard for a fast MARKET order.""",
    ],
    "symbol": [
        """Available symbols on Binance Futures Testnet:
- **BTCUSDT** — Bitcoin (most liquid, min qty 0.001)
- **ETHUSDT** — Ethereum (min qty 0.001)
- **BNBUSDT** — Binance Coin
- **SOLUSDT** — Solana
- **XRPUSDT** — Ripple
- **DOGEUSDT** — Dogecoin

All are USDT-margined perpetual futures. Use BTCUSDT for testing — it's the most stable on testnet.""",
    ],
    "log": [
        """The **Logs** tab shows the last 100 lines of `trading_bot.log`.

Each line contains:
- **Timestamp** — when it happened
- **Level** — INFO, DEBUG, WARNING, ERROR
- **Module** — which part of the code (bot.client, bot.orders, etc.)
- **Message** — what happened (API request, response body, order ID, errors)

The file rotates at 5 MB with 3 backups so it never gets too large.""",
    ],
    "error": [
        """Common errors and fixes:

**-2015 Invalid API Key** → Keys expired. Go to testnet.binancefuture.com → regenerate keys → update in Settings
**-1021 Timestamp** → Server clock skew. The bot auto-fixes this on startup.
**-4120 Order type not supported** → Use MARKET or LIMIT only on this testnet version.
**-1116 Invalid orderType** → Same as above — stick to MARKET and LIMIT.
**Validation error** → Check that quantity > 0 and price is provided for LIMIT orders.""",
    ],
    "keys": [
        """To get your Binance Futures Testnet API keys:

1. Go to **https://testnet.binancefuture.com**
2. Click **"Log In with GitHub"**
3. Click your **avatar → API Key → Generate Key**
4. Copy both the **API Key** (64 chars) and **Secret Key** (64 chars)
5. In this app: go to **Settings** tab → paste both keys → **Save & Connect**

Keys are stored only in your browser session — never sent anywhere except directly to Binance Testnet.""",
    ],
    "testnet": [
        """**Binance Futures Testnet** is a safe sandbox environment:

- URL: **testnet.binancefuture.com**
- Uses **fake USDT/BTC** — no real money at risk
- Real market data (prices reflect actual market)
- Your account starts with **5,000 USDT + 5,000 USDC + 0.01 BTC**
- API keys are separate from your real Binance account
- Keys expire periodically — just regenerate them if you get -2015 errors""",
    ],
    "price": [
        "I don't have a live price feed in this version. Check the ticker in the top bar for approximate prices. On testnet, BTC is usually around $107,000+. Use a limit order slightly above market to ensure it fills!",
    ],
    "status": [
        """**Order Statuses explained:**

- **NEW** — Order accepted and resting on the book (LIMIT orders)
- **FILLED** — Order fully executed
- **PARTIALLY_FILLED** — Some quantity filled, rest still open
- **CANCELED** — Order was cancelled
- **EXPIRED** — IOC/FOK order that couldn't fill and was auto-cancelled

For MARKET orders, they usually show NEW first then quickly become FILLED.""",
    ],
    "quantity": [
        """**Minimum quantities on Binance Futures Testnet:**

- **BTCUSDT** → min **0.001** BTC (~$107)
- **ETHUSDT** → min **0.001** ETH (~$3.84)
- **BNBUSDT** → min **0.01** BNB

Always use at least the minimum or you'll get a lot-size validation error. This bot validates your quantity before sending to the API.""",
    ],
    "profit": [
        "This bot runs on the **testnet** so there's no real P&L. But you can track your orders in the **Order History** tab to see what filled and at what price. For real trading performance tracking, you'd need a position management module!",
    ],
    "strategy": [
        """Here are some simple testnet strategies to try:

**1. Basic Market Order**
Buy BTC with a MARKET BUY, then place a LIMIT SELL above market price for profit.

**2. Limit Order Grid**
Place LIMIT BUYs at $100,000, $95,000, $90,000 to catch dips.

**3. IOC Test**
Use LIMIT_IOC with a price at the current market — it fills instantly like a market order but with price control.

Remember: this is testnet — experiment freely without any financial risk!""",
    ],
    "thankyou": [
        "You're welcome! Happy trading! Let me know if you need help with anything else.",
        "Glad I could help! Ask me anything anytime.",
        "Anytime! Good luck on the testnet!",
    ],
    "bye": [
        "Goodbye! Happy trading! Come back if you need help.",
        "See you later, trader! May your orders always fill!",
    ],
}

def ai_bot_respond(user_msg: str, connected: bool, order_count: int) -> str:
    """Rule-based AI bot that understands trading questions."""
    msg = user_msg.lower().strip()
    msg = re.sub(r'[^\w\s]', ' ', msg)

    # Match intent
    for intent, keywords in BOT_KNOWLEDGE.items():
        for kw in keywords:
            if kw in msg:
                replies = BOT_REPLIES.get(intent, [])
                if replies:
                    reply = random.choice(replies)
                    # Dynamic context injection
                    if intent == "balance" and not connected:
                        reply = "You're not connected yet! Go to **Settings** and enter your API keys first, then I can show you your real balance."
                    if intent == "place" and order_count > 0:
                        reply += f"\n\nYou've already placed **{order_count}** order(s) this session. Check Order History for details!"
                    return reply

    # Fallback
    return random.choice([
        "I'm not sure about that. Try asking me about: market orders, limit orders, API keys, balances, order status, or how to place a trade!",
        "Hmm, I didn't quite understand. I can help with: placing orders, checking balances, explaining order types, or setting up API keys. What do you need?",
        "That's a bit outside my knowledge base! Ask me about MARKET orders, LIMIT orders, IOC orders, balances, API keys, or trading strategies.",
    ])


@app.route("/api/chat", methods=["POST"])
def chat():
    data       = request.get_json()
    user_msg   = (data.get("message") or "").strip()
    connected  = bool(data.get("connected", False))
    order_count = int(data.get("order_count", 0))

    if not user_msg:
        return jsonify({"reply": "Please type a message!"}), 400

    logger.info("AI bot query: %s", user_msg[:80])
    reply = ai_bot_respond(user_msg, connected, order_count)
    return jsonify({"reply": reply})


if __name__ == "__main__":
    import os
    print("\n" + "="*60)
    print("  CryptoBot Pro — Web Interface")
    print("  Open: http://localhost:$PORT (or 5000 locally)")
    print("="*60 + "\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
