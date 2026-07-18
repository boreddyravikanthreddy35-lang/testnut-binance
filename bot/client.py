"""
Binance Futures Testnet REST client.

Wraps raw HMAC-SHA256 signed requests so that higher-level modules
never have to worry about authentication or low-level HTTP details.

Testnet base URL: https://testnet.binancefuture.com
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from .logging_config import get_logger

logger = get_logger(__name__)

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds
_server_time_offset_ms: int = 0   # corrected on first request


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    """
    Thin authenticated wrapper around the Binance Futures Testnet REST API.

    Usage:
        client = BinanceClient(api_key="...", api_secret="...")
        resp = client.post("/fapi/v1/order", {"symbol": "BTCUSDT", ...})
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.info("BinanceClient initialised (base_url=%s)", self._base_url)
        self._sync_time()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _sync_time(self) -> None:
        """Fetch server time once and compute offset to correct local clock skew."""
        global _server_time_offset_ms
        try:
            resp = requests.get(
                f"{self._base_url}/fapi/v1/time", timeout=self._timeout
            )
            server_ms = resp.json()["serverTime"]
            local_ms = int(time.time() * 1000)
            _server_time_offset_ms = server_ms - local_ms
            logger.debug("Server time offset: %d ms", _server_time_offset_ms)
        except Exception as exc:
            logger.warning("Could not sync server time: %s", exc)

    def _sign(self, params: dict) -> dict:
        """Add timestamp + HMAC-SHA256 signature to a params dict."""
        global _server_time_offset_ms
        params = dict(params)
        # Adjust for clock skew between local machine and testnet server
        params["timestamp"] = int(time.time() * 1000) + _server_time_offset_ms
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _handle_response(self, response: requests.Response) -> Any:
        """Parse JSON response, raise BinanceAPIError on non-2xx or API error body."""
        logger.debug(
            "HTTP %s %s → status=%s body=%s",
            response.request.method,
            response.url,
            response.status_code,
            response.text[:500],
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return response.text

        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        response.raise_for_status()
        return data

    # ── Public methods ─────────────────────────────────────────────────────────

    def get(
        self,
        path: str,
        params: Optional[dict] = None,
        signed: bool = True,
    ) -> Any:
        """
        Send an authenticated GET request.

        Args:
            path:   Full versioned path, e.g. "/fapi/v1/ping" or "/fapi/v2/balance"
            params: Query parameters (will be signed if signed=True)
            signed: Whether to add timestamp + HMAC signature
        """
        params = params or {}
        if signed:
            params = self._sign(params)
        url = f"{self._base_url}{path}"
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.info("GET %s params=%s", url, safe_params)
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error on GET %s: %s", url, exc)
            raise
        except requests.exceptions.Timeout:
            logger.error("Timeout on GET %s", url)
            raise
        return self._handle_response(resp)

    def post(
        self,
        path: str,
        params: Optional[dict] = None,
        signed: bool = True,
    ) -> Any:
        """
        Send an authenticated POST request.

        Args:
            path:   Full versioned path, e.g. "/fapi/v1/order"
            params: Body parameters (will be signed if signed=True)
            signed: Whether to add timestamp + HMAC signature
        """
        params = params or {}
        if signed:
            params = self._sign(params)
        url = f"{self._base_url}{path}"
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.info("POST %s params=%s", url, safe_params)
        try:
            resp = self._session.post(url, data=params, timeout=self._timeout)
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error on POST %s: %s", url, exc)
            raise
        except requests.exceptions.Timeout:
            logger.error("Timeout on POST %s", url)
            raise
        return self._handle_response(resp)

    # ── Convenience methods ────────────────────────────────────────────────────

    def get_account_info(self) -> list:
        """Fetch current futures account balances (v2 endpoint)."""
        return self.get("/fapi/v2/balance")

    def get_exchange_info(self) -> dict:
        """Fetch exchange trading rules and symbol info (no auth required)."""
        return self.get("/fapi/v1/exchangeInfo", signed=False)
