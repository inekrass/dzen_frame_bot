"""Tests for environment-based application configuration."""

from pathlib import Path

import pytest

from dzen_frame_bot.config import ConfigurationError, Settings


def test_settings_accept_required_token() -> None:
    settings = Settings.from_mapping({"BOT_TOKEN": "test-token"})

    assert settings.bot_token == "test-token"
    assert settings.admin_ids == frozenset()
    assert settings.stats_db_path == Path("data/stats.sqlite3")
    assert settings.log_level == "INFO"


def test_settings_normalize_values() -> None:
    settings = Settings.from_mapping(
        {"BOT_TOKEN": "  test-token  ", "LOG_LEVEL": "debug"}
    )

    assert settings.bot_token == "test-token"
    assert settings.log_level == "DEBUG"


def test_settings_reject_missing_token() -> None:
    with pytest.raises(ConfigurationError, match="BOT_TOKEN is required"):
        Settings.from_mapping({})


def test_settings_reject_unknown_log_level() -> None:
    with pytest.raises(ConfigurationError, match="LOG_LEVEL must be one of"):
        Settings.from_mapping({"BOT_TOKEN": "test-token", "LOG_LEVEL": "verbose"})


def test_settings_parse_admin_ids_and_database_path() -> None:
    settings = Settings.from_mapping(
        {
            "BOT_TOKEN": "test-token",
            "ADMIN_IDS": "123, 456,123",
            "STATS_DB_PATH": "local/stats.db",
        }
    )

    assert settings.admin_ids == frozenset({123, 456})
    assert settings.stats_db_path == Path("local/stats.db")


@pytest.mark.parametrize("admin_ids", ["abc", "1,two", "-5", "0"])
def test_settings_reject_invalid_admin_ids(admin_ids: str) -> None:
    with pytest.raises(ConfigurationError, match="ADMIN_IDS"):
        Settings.from_mapping({"BOT_TOKEN": "test-token", "ADMIN_IDS": admin_ids})
