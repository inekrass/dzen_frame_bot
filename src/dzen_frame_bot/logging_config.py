"""Safe application logging configuration."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str) -> None:
    """Configure concise logs without Telegram update payloads or photo data."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
