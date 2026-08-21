"""Tests for aggregate SQLite statistics and admin access."""

import asyncio
import sqlite3
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from dzen_frame_bot.handlers.admin import (
    extract_custom_emoji_ids,
    format_stats,
    handle_emoji_ids,
    handle_my_id,
    handle_stats,
)
from dzen_frame_bot.stats import (
    StatsCounters,
    StatsEvent,
    StatsRepository,
    StatsSnapshot,
)
from dzen_frame_bot.texts import ACCESS_DENIED_TEXT, CUSTOM_EMOJI_NOT_FOUND_TEXT


def test_repository_aggregates_daily_and_total_counters(tmp_path) -> None:
    database_path = tmp_path / "stats.sqlite3"
    repository = StatsRepository(database_path)
    first_day = date(2026, 8, 20)
    second_day = date(2026, 8, 21)

    repository.increment(StatsEvent.START, first_day)
    repository.increment(StatsEvent.PROCESSED, first_day)
    repository.increment(StatsEvent.START, second_day)
    repository.increment(StatsEvent.UPLOAD_REQUEST, second_day)
    repository.increment(StatsEvent.PROCESSED, second_day)
    repository.increment(StatsEvent.CENTERED, second_day)

    snapshot = repository.snapshot(second_day)

    assert snapshot.today == StatsCounters(
        starts=1,
        upload_requests=1,
        processed=1,
        centered=1,
    )
    assert snapshot.total == StatsCounters(
        starts=2,
        upload_requests=1,
        processed=2,
        centered=1,
    )


def test_database_schema_contains_no_user_or_file_identifiers(tmp_path) -> None:
    database_path = tmp_path / "stats.sqlite3"
    StatsRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(daily_stats)")
        }

    assert columns == {
        "day",
        "starts",
        "upload_requests",
        "profile_requests",
        "processed",
        "centered",
        "errors",
    }


def test_unauthorized_user_cannot_read_stats() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=10)
    stats_service = AsyncMock()

    asyncio.run(handle_stats(message, stats_service, frozenset({20})))

    message.answer.assert_awaited_once_with(ACCESS_DENIED_TEXT)
    stats_service.snapshot.assert_not_awaited()


def test_authorized_user_receives_aggregate_report() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=10)
    stats_service = AsyncMock()
    snapshot = StatsSnapshot(
        day=date(2026, 8, 21),
        today=StatsCounters(starts=2, processed=1),
        total=StatsCounters(starts=5, processed=4),
    )
    stats_service.snapshot.return_value = snapshot

    asyncio.run(handle_stats(message, stats_service, frozenset({10})))

    message.answer.assert_awaited_once_with(format_stats(snapshot))


def test_myid_returns_id_without_storage() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=123456)

    asyncio.run(handle_my_id(message))

    message.answer.assert_awaited_once_with("Ваш Telegram ID: 123456")


def test_unauthorized_user_cannot_read_custom_emoji_ids() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=10)

    asyncio.run(handle_emoji_ids(message, frozenset({20})))

    message.answer.assert_awaited_once_with(ACCESS_DENIED_TEXT)


def test_authorized_user_receives_unique_custom_emoji_ids() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=10)
    message.reply_to_message = None
    message.entities = [
        SimpleNamespace(type="bot_command", custom_emoji_id=None),
        SimpleNamespace(type="custom_emoji", custom_emoji_id="111"),
        SimpleNamespace(type="custom_emoji", custom_emoji_id="111"),
        SimpleNamespace(type="custom_emoji", custom_emoji_id="222"),
    ]
    message.caption_entities = None

    asyncio.run(handle_emoji_ids(message, frozenset({10})))

    message.answer.assert_awaited_once_with(
        "ID кастомных эмодзи:\n1. 111\n2. 222"
    )


def test_custom_emoji_ids_can_be_read_from_replied_caption() -> None:
    replied_message = SimpleNamespace(
        entities=None,
        caption_entities=[
            SimpleNamespace(type="custom_emoji", custom_emoji_id="333")
        ],
    )

    assert extract_custom_emoji_ids(replied_message) == ("333",)


def test_authorized_user_gets_instructions_without_custom_emoji() -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=10)
    message.reply_to_message = None
    message.entities = []
    message.caption_entities = None

    asyncio.run(handle_emoji_ids(message, frozenset({10})))

    message.answer.assert_awaited_once_with(CUSTOM_EMOJI_NOT_FOUND_TEXT)
