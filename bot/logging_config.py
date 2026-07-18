"""
Logging configuration for the Binance Futures Trading Bot.
Sets up both file and console handlers with structured formatting.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure root logger with:
      - RotatingFileHandler  → logs/trading_bot.log  (max 5 MB × 3 backups)
      - StreamHandler        → console (WARNING and above to keep CLI output clean)

    Args:
        level: Log level string for the file handler (DEBUG/INFO/WARNING/ERROR).

    Returns:
        Configured root logger.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)          # capture everything; handlers filter

    # ── File handler ──────────────────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)    # only warnings/errors to terminal
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # Avoid duplicate handlers on repeated calls (e.g. during tests)
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger (call after setup_logging())."""
    return logging.getLogger(name)
