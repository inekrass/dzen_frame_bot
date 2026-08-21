"""Command-line entry point for the bot."""

from __future__ import annotations

import asyncio
import sys

from dzen_frame_bot.config import ConfigurationError, load_settings
from dzen_frame_bot.logging_config import configure_logging


def main() -> None:
    """Load configuration and start the Telegram polling loop."""
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    from dzen_frame_bot.bot import run_bot

    configure_logging(settings.log_level)
    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
