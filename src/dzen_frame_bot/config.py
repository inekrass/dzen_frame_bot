"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

SUPPORTED_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class ConfigurationError(RuntimeError):
    """Raised when required application settings are invalid or missing."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings without any persisted user data."""

    bot_token: str
    log_level: str = "INFO"

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        """Create settings from a mapping such as ``os.environ``."""
        bot_token = values.get("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ConfigurationError("BOT_TOKEN is required")

        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in SUPPORTED_LOG_LEVELS:
            supported = ", ".join(sorted(SUPPORTED_LOG_LEVELS))
            raise ConfigurationError(f"LOG_LEVEL must be one of: {supported}")

        return cls(bot_token=bot_token, log_level=log_level)


def load_settings() -> Settings:
    """Load local ``.env`` values without overriding process environment."""
    load_dotenv(override=False)
    return Settings.from_mapping(os.environ)
