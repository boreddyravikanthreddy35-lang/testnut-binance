"""
bot package — Binance Futures Testnet trading bot core modules.

Modules:
  client          – Authenticated REST client (HMAC-SHA256)
  orders          – OrderManager + OrderResult
  validators      – Input validation helpers
  logging_config  – File + console logging setup
"""

from .logging_config import setup_logging, get_logger
from .client import BinanceClient, BinanceAPIError
from .orders import OrderManager, OrderResult
from .validators import validate_all, ValidationError

__all__ = [
    "setup_logging",
    "get_logger",
    "BinanceClient",
    "BinanceAPIError",
    "OrderManager",
    "OrderResult",
    "validate_all",
    "ValidationError",
]
