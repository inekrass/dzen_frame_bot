"""Tests for environment-based application configuration."""

import pytest

from dzen_frame_bot.config import ConfigurationError, Settings


def test_settings_accept_required_token() -> None:
    settings = Settings.from_mapping({"BOT_TOKEN": "test-token"})

    assert settings.bot_token == "test-token"
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
