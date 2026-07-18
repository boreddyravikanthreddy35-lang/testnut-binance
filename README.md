# Binance Futures Testnet Trading Bot

A clean, production-style **Python CLI application** that places **MARKET**, **LIMIT**, and **LIMIT_IOC** orders on the [Binance Futures Testnet](https://testnet.binancefuture.com) (USDT-M perpetuals).

Built as part of the Python Developer application task. No external Binance SDK — uses direct REST calls with HMAC-SHA256 authentication.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py           # Package exports
│   ├── client.py             # HMAC-SHA256 authenticated REST client + server-time sync
│   ├── orders.py             # OrderManager class + OrderResult dataclass
│   ├── validators.py         # CLI input validation (raises ValidationError)
│   └── logging_config.py     # Rotating file + console logging setup
├── logs/
│   └── trading_bot.log       # Real log output from live testnet session
├── webapp/                   # Bonus: Flask web UI + AI chatbot
│   ├── app.py
│   ├── templates/index.html
│   └── static/
├── cli.py                    # CLI entry point (argparse)
├── .env.example              # Credential template — copy to .env
├── requirements.txt
└── README.md
```

---

## Setup Steps

### 1 · Prerequisites

- Python **3.9+**
- A free [GitHub account](https://github.com) (needed to log in to testnet)

### 2 · Clone / unzip and install dependencies

```bash
cd trading_bot
pip install -r requirements.txt
```

### 3 · Get Testnet API credentials

1. Go to **[https://testnet.binancefuture.com](https://testnet.binancefuture.com)**
2. Click **"Log In with GitHub"** and authorise
3. Click your **avatar (top-right)** → **"API Key"** → **"Generate Key"**
4. Copy both the **API Key** and **Secret Key** (secret shown **only once**)

### 4 · Create your `.env` file

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open `.env` and paste your keys:

```env
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

> ⚠ Never commit `.env` to Git — it is already in `.gitignore`.

---

## How to Run Examples

All commands are run from inside the `trading_bot/` directory.

### Check account balance (optional — verify connection)

```bash
python cli.py --check-balance
```

Output:
```
Fetching account balance from testnet...

  Asset               Balance        Available
  ---------- ---------------- ----------------
  BTC                  0.0100           0.0100
  USDT              5000.0000        5000.0000
  USDC              5000.0000        5000.0000
```

---

### Place a MARKET order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

Output:
```
==================================================
  ORDER REQUEST SUMMARY
==================================================
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
==================================================

Placing MARKET order on Binance Futures Testnet...

==================================================
  [OK] Order placed successfully
==================================================
  Order ID       : 22237386762
  Client OID     : EHLTCqoQuoMYnFQ3uNIOqF
  Symbol         : BTCUSDT
  Side           : BUY
  Type           : MARKET
  Status         : NEW
  Orig Qty       : 0.0010
  Executed Qty   : 0.0000
==================================================
```

---

### Place a LIMIT order

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000
```

Output:
```
==================================================
  ORDER REQUEST SUMMARY
==================================================
  Symbol     : BTCUSDT
  Side       : SELL
  Type       : LIMIT
  Quantity   : 0.001
  Price      : 100000
==================================================

Placing LIMIT order on Binance Futures Testnet...

==================================================
  [OK] Order placed successfully
==================================================
  Order ID       : 22237371949
  Client OID     : cJCI7Jro2bQsg7ZoXUpnYV
  Symbol         : BTCUSDT
  Side           : SELL
  Type           : LIMIT
  Status         : NEW
  Orig Qty       : 0.0010
  Executed Qty   : 0.0000
  Limit Price    : 100000.00
  Time-In-Force  : GTC
==================================================
```

---

### Place a LIMIT_IOC order (Bonus — 3rd order type)

```bash
python cli.py --symbol BTCUSDT --side BUY --type LIMIT_IOC --quantity 0.001 --price 50000
```

Output:
```
==================================================
  ORDER REQUEST SUMMARY
==================================================
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : LIMIT_IOC
  Quantity   : 0.001
  Price      : 50000
==================================================

Placing LIMIT_IOC order on Binance Futures Testnet...

==================================================
  [OK] Order placed successfully
==================================================
  Order ID       : 22237377097
  Symbol         : BTCUSDT
  Side           : BUY
  Type           : LIMIT
  Status         : NEW
  Orig Qty       : 0.0010
  Time-In-Force  : IOC
==================================================
```

---

### All CLI Flags

| Flag | Required | Description | Example |
|---|---|---|---|
| `--symbol` / `-s` | Yes* | Trading pair symbol | `BTCUSDT` |
| `--side` | Yes* | Order direction | `BUY` or `SELL` |
| `--type` / `-t` | Yes* | Order type | `MARKET`, `LIMIT`, `LIMIT_IOC` |
| `--quantity` / `-q` | Yes* | Order quantity | `0.001` |
| `--price` / `-p` | LIMIT only | Limit price | `100000` |
| `--time-in-force` | No | GTC (default) / IOC / FOK | `GTC` |
| `--check-balance` | — | Print account balances and exit | — |
| `--log-level` | No | File log verbosity | `DEBUG` (default) |

\* Required for placing orders (not needed for `--check-balance`).

---

## Logging

All API requests, responses, and errors are written to:

```
trading_bot/logs/trading_bot.log
```

| Handler | Level | Destination |
|---|---|---|
| File handler | DEBUG (full detail) | `logs/trading_bot.log` |
| Console handler | WARNING and above | Terminal (keeps output clean) |

The log file rotates at **5 MB**, keeping **3 backups** (`trading_bot.log.1`, `.2`, `.3`).

**Sample log lines:**
```
2026-07-17 08:41:40 | INFO     | bot.client | BinanceClient initialised
2026-07-17 08:41:40 | DEBUG    | bot.client | Server time offset: 13789 ms
2026-07-17 08:41:40 | INFO     | bot.orders | Order request: {"symbol":"BTCUSDT","side":"BUY","type":"MARKET","quantity":"0.001"}
2026-07-17 08:41:40 | INFO     | bot.client | POST https://testnet.binancefuture.com/fapi/v1/order
2026-07-17 08:41:41 | DEBUG    | bot.client | HTTP POST ... status=200 body={"orderId":22237386762,...}
2026-07-17 08:41:41 | INFO     | bot.orders | Order response: orderId=22237386762 status=NEW executedQty=0.0000
2026-07-17 08:41:41 | INFO     | __main__   | Order completed successfully. orderId=22237386762
```

---

## Assumptions

1. **Testnet only** — Base URL is hardcoded to `https://testnet.binancefuture.com`. No real funds are ever used or at risk.

2. **USDT-M perpetuals** — All symbols are USDT-margined perpetual futures (e.g. `BTCUSDT`, `ETHUSDT`).

3. **Minimum quantity** — The testnet enforces the same lot-size filters as mainnet. Minimum quantity for `BTCUSDT` is `0.001`.

4. **Supported order types** — The Binance Futures Testnet `/fapi/v1/order` endpoint currently only supports `MARKET` and `LIMIT`. All conditional types (`STOP_MARKET`, `TAKE_PROFIT_MARKET`, `LIMIT_MAKER`) return error `-4120` on this testnet instance as they have been moved to a separate Algo Order API. The bonus 3rd order type is **LIMIT_IOC** (a LIMIT order with `timeInForce=IOC`).

5. **No external SDK** — Only `requests` and `python-dotenv` are used. No `python-binance` library required.

6. **Credentials via `.env`** — API keys are loaded from a local `.env` file via `python-dotenv`. Keys are never hardcoded or logged.

7. **Server-time sync** — The bot fetches server time on startup and applies an offset to all timestamps to prevent `-1021` clock-skew errors.

---

## Bonus: Web UI

A Flask-based web interface is included in `webapp/`:

```bash
cd trading_bot/webapp
python app.py
```

Open **(https://testnut-binance-4.onrender.com)** to:
- Place orders from a browser UI
- Check live balances
- View order history
- Stream live logs
- Chat with the **AI Trading Assistant** (answers questions about order types, errors, strategies)

---

## Live Order Evidence

The following real order IDs were placed during development on Binance Futures Testnet:

| Order ID | Type | Side | Price | Status |
|---|---|---|---|---|
| 22237386762 | MARKET | BUY | Market | NEW |
| 22237371949 | LIMIT | SELL | $100,000 | NEW |
| 22237377097 | LIMIT_IOC | BUY | $50,000 | NEW |
| 22225287805 | LIMIT | SELL | $100,000 | NEW |
| 22225283684 | MARKET | BUY | Market | NEW |

All orders logged in `logs/trading_bot.log`.
