"""
CLI entry point for the Binance Futures Testnet Trading Bot.

Usage examples:
  python cli.py --symbol BTCUSDT --side BUY  --type MARKET --quantity 0.001
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT  --quantity 0.001 --price 50000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 40000
  python cli.py --check-balance
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

# ── bootstrap: make sure the package is importable when run as a script ────────
sys.path.insert(0, os.path.dirname(__file__))

from bot.logging_config import setup_logging, get_logger
from bot.validators import validate_all, ValidationError
from bot.client import BinanceClient, BinanceAPIError
from bot.orders import OrderManager

# Load .env — try script directory first, fall back to cwd (covers both
# `python cli.py` from inside the folder and module invocation)
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))
load_dotenv(os.path.join(os.getcwd(), ".env"))   # fallback

# ── Logger (set up before any usage) ──────────────────────────────────────────
setup_logging(level="DEBUG")
logger = get_logger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _print_request_summary(args: argparse.Namespace) -> None:
    """Print a formatted order request summary to stdout."""
    print()
    print("=" * 50)
    print("  ORDER REQUEST SUMMARY")
    print("=" * 50)
    print(f"  Symbol     : {args.symbol.upper()}")
    print(f"  Side       : {args.side.upper()}")
    print(f"  Type       : {args.type.upper()}")
    print(f"  Quantity   : {args.quantity}")
    if args.price:
        print(f"  Price      : {args.price}")
    if hasattr(args, "stop_price") and args.stop_price:
        print(f"  Stop Price : {args.stop_price}")
    print("=" * 50)


def _build_client() -> BinanceClient:
    """Read API credentials from environment and return a BinanceClient."""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(
            "\n[ERROR] API credentials not found.\n"
            "  Create a .env file in the trading_bot/ directory:\n\n"
            "    BINANCE_API_KEY=your_key_here\n"
            "    BINANCE_API_SECRET=your_secret_here\n"
        )
        logger.error("Missing BINANCE_API_KEY or BINANCE_API_SECRET in environment.")
        sys.exit(1)

    return BinanceClient(api_key=api_key, api_secret=api_secret)


def _check_balance(client: BinanceClient) -> None:
    """Fetch and print the testnet account balance."""
    print("\nFetching account balance from testnet...\n")
    try:
        assets = client.get_account_info()   # v2/balance returns a list
        if not assets:
            print("  No asset data returned.")
            return
        print(f"  {'Asset':<10} {'Balance':>16} {'Available':>16}")
        print(f"  {'-'*10} {'-'*16} {'-'*16}")
        for a in assets:
            bal = float(a.get("balance", 0))
            avail = float(a.get("availableBalance", 0))
            if bal > 0 or avail > 0:
                print(f"  {a['asset']:<10} {bal:>16.4f} {avail:>16.4f}")
        print()
    except BinanceAPIError as exc:
        print(f"\n[ERROR] {exc}\n")
        logger.error("Failed to fetch account info: %s", exc)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Network or unexpected error: {exc}\n")
        logger.error("Unexpected error fetching account info: %s", exc, exc_info=True)
        sys.exit(1)


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description=(
            "Binance Futures Testnet Trading Bot\n"
            "Place MARKET, LIMIT, or LIMIT_MAKER orders via the CLI."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Market buy\n"
            "  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001\n\n"
            "  # Limit sell\n"
            "  python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000\n\n"
            "  # Limit-maker (post-only) sell -- bonus order type\n"
            "  python cli.py --symbol BTCUSDT --side SELL --type LIMIT_MAKER --quantity 0.001 --price 200000\n\n"
            "  # Check account balance\n"
            "  python cli.py --check-balance\n"
        ),
    )

    parser.add_argument(
        "--symbol", "-s",
        type=str,
        help="Trading pair symbol, e.g. BTCUSDT",
    )
    parser.add_argument(
        "--side",
        type=str,
        choices=["BUY", "SELL", "buy", "sell"],
        help="Order side: BUY or SELL",
    )
    parser.add_argument(
        "--type", "-t",
        dest="type",
        type=str,
        choices=["MARKET", "LIMIT", "LIMIT_IOC", "market", "limit", "limit_ioc"],
        help="Order type: MARKET | LIMIT | LIMIT_IOC (immediate-or-cancel, bonus type)",
    )
    parser.add_argument(
        "--quantity", "-q",
        type=str,
        help="Order quantity (e.g. 0.001)",
    )
    parser.add_argument(
        "--price", "-p",
        type=str,
        default=None,
        help="Limit price (required for LIMIT orders)",
    )
    parser.add_argument(
        "--stop-price",
        dest="stop_price",
        type=str,
        default=None,
        help="(Legacy flag, kept for compatibility)",
    )
    parser.add_argument(
        "--time-in-force",
        dest="time_in_force",
        type=str,
        default="GTC",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC)",
    )
    parser.add_argument(
        "--check-balance",
        action="store_true",
        help="Print current testnet account balances and exit",
    )
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="File log level (default: DEBUG)",
    )

    return parser


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Rebuild logger with user-specified level
    setup_logging(level=args.log_level)
    logger.debug("CLI args received: %s", vars(args))

    client = _build_client()

    # ── Balance check mode ─────────────────────────────────────────────────────
    if args.check_balance:
        _check_balance(client)
        sys.exit(0)

    # ── Order mode: require all order fields ───────────────────────────────────
    missing = [f for f, v in [("--symbol", args.symbol), ("--side", args.side),
                               ("--type", args.type), ("--quantity", args.quantity)] if not v]
    if missing:
        parser.error(
            f"The following arguments are required for placing an order: {', '.join(missing)}"
        )

    # ── Validate inputs ────────────────────────────────────────────────────────
    try:
        params = validate_all(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValidationError as exc:
        print(f"\n[VALIDATION ERROR] {exc}\n")
        logger.warning("Validation failed: %s", exc)
        sys.exit(1)

    # ── Print request summary ──────────────────────────────────────────────────
    _print_request_summary(args)

    # ── Place order ────────────────────────────────────────────────────────────
    manager = OrderManager(client)
    order_type = params["order_type"]

    print(f"\nPlacing {order_type} order on Binance Futures Testnet...\n")
    logger.info("Placing %s order: symbol=%s side=%s qty=%s",
                order_type, params["symbol"], params["side"], params["quantity"])

    if order_type == "MARKET":
        result = manager.place_market_order(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
        )
    elif order_type == "LIMIT":
        result = manager.place_limit_order(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
            price=params["price"],
            time_in_force=args.time_in_force,
        )
    elif order_type == "LIMIT_IOC":
        result = manager.place_limit_ioc_order(
            symbol=params["symbol"],
            side=params["side"],
            quantity=params["quantity"],
            price=params["price"],
        )

    # ── Print result ───────────────────────────────────────────────────────────
    print(result.pretty())

    if not result.success:
        logger.error("Order placement failed. See above for details.")
        sys.exit(1)

    logger.info("Order completed successfully. orderId=%s", result.order_id)


if __name__ == "__main__":
    main()
