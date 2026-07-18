"""
Input validation for CLI arguments before they reach the Binance API.
All validators raise ValueError with a human-readable message on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

# ── Allowed values ─────────────────────────────────────────────────────────────
VALID_SIDES = {"BUY", "SELL"}
# NOTE: Binance Futures Testnet /fapi/v1/order only supports MARKET and LIMIT.
# All conditional types (STOP_MARKET, TAKE_PROFIT_MARKET, LIMIT_MAKER, etc.)
# return -4120 or -1116 on this testnet instance.
# The bonus order type is LIMIT_IOC: a LIMIT order with timeInForce=IOC
# (Immediate-Or-Cancel — fills what it can instantly, cancels the rest).
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "LIMIT_IOC"}


class ValidationError(ValueError):
    """Raised when user-supplied input fails validation."""


def validate_symbol(symbol: str) -> str:
    """
    Normalise and validate a trading pair symbol.

    Rules:
      - Non-empty string
      - Uppercase only
      - Minimum 6 characters (e.g. BTCUSDT)

    Returns the normalised (uppercased) symbol.
    """
    if not symbol or not symbol.strip():
        raise ValidationError("Symbol must not be empty.")
    cleaned = symbol.strip().upper()
    if len(cleaned) < 6:
        raise ValidationError(
            f"Symbol '{cleaned}' looks too short. Expected something like 'BTCUSDT'."
        )
    if not cleaned.isalpha():
        raise ValidationError(
            f"Symbol '{cleaned}' must contain only letters (e.g. BTCUSDT)."
        )
    return cleaned


def validate_side(side: str) -> str:
    """
    Validate order side.

    Returns normalised uppercase side string.
    """
    if not side or not side.strip():
        raise ValidationError("Side must not be empty.")
    normalised = side.strip().upper()
    if normalised not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{normalised}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return normalised


def validate_order_type(order_type: str) -> str:
    """
    Validate order type.

    Returns normalised uppercase order type string.
    """
    if not order_type or not order_type.strip():
        raise ValidationError("Order type must not be empty.")
    normalised = order_type.strip().upper()
    if normalised not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{normalised}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return normalised


def validate_quantity(quantity: str | float) -> Decimal:
    """
    Validate and parse order quantity.

    Rules:
      - Must be a valid positive number
      - Must be > 0
    """
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValidationError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValidationError(f"Quantity must be greater than zero, got {qty}.")
    return qty


def validate_price(price: Optional[str | float]) -> Optional[Decimal]:
    """
    Validate and parse limit price.

    Rules:
      - None is acceptable (for MARKET orders)
      - If provided, must be a valid positive number
    """
    if price is None:
        return None
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValidationError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValidationError(f"Price must be greater than zero, got {p}.")
    return p


def validate_stop_price(stop_price: Optional[str | float]) -> Optional[Decimal]:
    """Validate and parse stop price (used for STOP_MARKET orders)."""
    if stop_price is None:
        return None
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValidationError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValidationError(f"Stop price must be greater than zero, got {sp}.")
    return sp


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> dict:
    """
    Run all validations and return a clean params dict.

    Raises ValidationError on the first invalid field.
    """
    params: dict = {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
    }

    ot = params["order_type"]

    # Price is required for LIMIT and LIMIT_IOC orders
    if ot in ("LIMIT", "LIMIT_IOC"):
        if price is None:
            raise ValidationError(f"Price is required for {ot} orders.")
        params["price"] = validate_price(price)
    else:
        params["price"] = validate_price(price)  # optional, may be None

    params["stop_price"] = validate_stop_price(stop_price)  # always optional now

    return params
