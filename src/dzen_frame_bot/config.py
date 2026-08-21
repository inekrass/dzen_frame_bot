"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SUPPORTED_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class ConfigurationError(RuntimeError):
    """Raised when required application settings are invalid or missing."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings without any persisted user data."""

    bot_token: str
    admin_ids: frozenset[int] = frozenset()
    stats_db_path: Path = Path("data/stats.sqlite3")
    log_level: str = "INFO"

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        """Create settings from a mapping such as ``os.environ``."""
        bot_token = values.get("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ConfigurationError("BOT_TOKEN is required")

        admin_ids = _parse_admin_ids(values.get("ADMIN_IDS", ""))
        stats_db_path_value = values.get("STATS_DB_PATH", "").strip()
        stats_db_path = Path(stats_db_path_value or "data/stats.sqlite3")

        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in SUPPORTED_LOG_LEVELS:
            supported = ", ".join(sorted(SUPPORTED_LOG_LEVELS))
            raise ConfigurationError(f"LOG_LEVEL must be one of: {supported}")

        return cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            stats_db_path=stats_db_path,
            log_level=log_level,
        )


def _parse_admin_ids(raw_value: str) -> frozenset[int]:
    if not raw_value.strip():
        return frozenset()

    try:
        admin_ids = frozenset(
            int(part.strip()) for part in raw_value.split(",") if part.strip()
        )
    except ValueError as error:
        message = "ADMIN_IDS must contain comma-separated integers"
        raise ConfigurationError(message) from error

    if any(admin_id <= 0 for admin_id in admin_ids):
        raise ConfigurationError("ADMIN_IDS must contain positive integers")
    return admin_ids


def load_settings() -> Settings:
    """Load local ``.env`` values without overriding process environment."""
    load_dotenv(override=False)
    return Settings.from_mapping(os.environ)
