"""
Order placement logic for Binance Futures Testnet.

This module provides a clean OrderManager class that:
  - accepts validated parameters
  - calls the BinanceClient
  - returns a structured OrderResult dataclass
  - logs every step at the appropriate level
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .client import BinanceClient, BinanceAPIError
from .logging_config import get_logger

logger = get_logger(__name__)


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class OrderResult:
    """Structured representation of a placed order response."""

    success: bool
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    status: Optional[str] = None
    price: Optional[str] = None
    avg_price: Optional[str] = None
    orig_qty: Optional[str] = None
    executed_qty: Optional[str] = None
    time_in_force: Optional[str] = None
    raw_response: dict = field(default_factory=dict)
    error_message: Optional[str] = None

    def pretty(self) -> str:
        """Return a formatted multi-line summary suitable for CLI output."""
        if not self.success:
            return (
                f"\n{'='*50}\n"
                f"  [FAILED] Order FAILED\n"
                f"  Error : {self.error_message}\n"
                f"{'='*50}\n"
            )
        lines = [
            f"\n{'='*50}",
            f"  [OK] Order placed successfully",
            f"{'='*50}",
            f"  Order ID       : {self.order_id}",
            f"  Client OID     : {self.client_order_id}",
            f"  Symbol         : {self.symbol}",
            f"  Side           : {self.side}",
            f"  Type           : {self.order_type}",
            f"  Status         : {self.status}",
            f"  Orig Qty       : {self.orig_qty}",
            f"  Executed Qty   : {self.executed_qty}",
        ]
        if self.price and self.price != "0":
            lines.append(f"  Limit Price    : {self.price}")
        if self.avg_price and self.avg_price != "0":
            lines.append(f"  Avg Fill Price : {self.avg_price}")
        if self.time_in_force:
            lines.append(f"  Time-In-Force  : {self.time_in_force}")
        lines.append(f"{'='*50}\n")
        return "\n".join(lines)


# ── OrderManager ───────────────────────────────────────────────────────────────

class OrderManager:
    """
    Handles all order operations against Binance Futures.

    Args:
        client: An authenticated BinanceClient instance.
    """

    def __init__(self, client: BinanceClient) -> None:
        self._client = client

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: dict) -> OrderResult:
        """Map raw Binance API response dict to an OrderResult."""
        return OrderResult(
            success=True,
            order_id=raw.get("orderId"),
            client_order_id=raw.get("clientOrderId"),
            symbol=raw.get("symbol"),
            side=raw.get("side"),
            order_type=raw.get("type") or raw.get("origType"),
            status=raw.get("status"),
            price=raw.get("price"),
            avg_price=raw.get("avgPrice"),
            orig_qty=raw.get("origQty"),
            executed_qty=raw.get("executedQty"),
            time_in_force=raw.get("timeInForce"),
            raw_response=raw,
        )

    def _log_request(self, params: dict) -> None:
        safe = {k: v for k, v in params.items() if k not in ("signature",)}
        logger.info("Order request: %s", json.dumps(safe, default=str))

    def _log_response(self, result: OrderResult) -> None:
        if result.success:
            logger.info(
                "Order response: orderId=%s status=%s executedQty=%s avgPrice=%s",
                result.order_id,
                result.status,
                result.executed_qty,
                result.avg_price,
            )
        else:
            logger.error("Order failed: %s", result.error_message)

    # ── Public order methods ───────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> OrderResult:
        """
        Place a MARKET order on Binance Futures Testnet.

        Args:
            symbol:   Trading pair (e.g. "BTCUSDT")
            side:     "BUY" or "SELL"
            quantity: Order quantity

        Returns:
            OrderResult with success/failure details.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": str(quantity),
        }
        self._log_request(params)

        try:
            raw = self._client.post("/fapi/v1/order", params)
            result = self._parse_response(raw)
            self._log_response(result)
            return result
        except BinanceAPIError as exc:
            logger.error("BinanceAPIError placing MARKET order: %s", exc)
            return OrderResult(success=False, error_message=str(exc))
        except Exception as exc:
            logger.error("Unexpected error placing MARKET order: %s", exc, exc_info=True)
            return OrderResult(success=False, error_message=f"Unexpected error: {exc}")

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """
        Place a LIMIT order on Binance Futures Testnet.

        Args:
            symbol:         Trading pair (e.g. "BTCUSDT")
            side:           "BUY" or "SELL"
            quantity:       Order quantity
            price:          Limit price
            time_in_force:  GTC (default) | IOC | FOK

        Returns:
            OrderResult with success/failure details.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": str(quantity),
            "price": str(price),
            "timeInForce": time_in_force,
        }
        self._log_request(params)

        try:
            raw = self._client.post("/fapi/v1/order", params)
            result = self._parse_response(raw)
            self._log_response(result)
            return result
        except BinanceAPIError as exc:
            logger.error("BinanceAPIError placing LIMIT order: %s", exc)
            return OrderResult(success=False, error_message=str(exc))
        except Exception as exc:
            logger.error("Unexpected error placing LIMIT order: %s", exc, exc_info=True)
            return OrderResult(success=False, error_message=f"Unexpected error: {exc}")

    def place_limit_ioc_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> OrderResult:
        """
        Place a LIMIT IOC (Immediate-Or-Cancel) order — bonus order type.

        An IOC order fills as much as possible at the limit price immediately.
        Any unfilled portion is cancelled automatically. This is a distinct
        execution behaviour from a standard GTC LIMIT order and is the third
        supported order type on this testnet instance.

        Note: Binance Futures Testnet /fapi/v1/order only supports MARKET and
        LIMIT (with timeInForce GTC/IOC). All conditional types (STOP_MARKET,
        TAKE_PROFIT_MARKET, LIMIT_MAKER) return -4120/-1116 on this testnet.

        Args:
            symbol:   Trading pair
            side:     "BUY" or "SELL"
            quantity: Order quantity
            price:    Limit price

        Returns:
            OrderResult with success/failure details.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "IOC",
            "quantity": str(quantity),
            "price": str(price),
        }
        self._log_request(params)

        try:
            raw = self._client.post("/fapi/v1/order", params)
            result = self._parse_response(raw)
            self._log_response(result)
            return result
        except BinanceAPIError as exc:
            logger.error("BinanceAPIError placing LIMIT_IOC order: %s", exc)
            return OrderResult(success=False, error_message=str(exc))
        except Exception as exc:
            logger.error("Unexpected error placing LIMIT_IOC order: %s", exc, exc_info=True)
            return OrderResult(success=False, error_message=f"Unexpected error: {exc}")
