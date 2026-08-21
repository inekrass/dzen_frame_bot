"""Tests for Telegram flow helpers and short-lived guards."""

import asyncio
from unittest.mock import AsyncMock

from aiogram.types import PhotoSize

from dzen_frame_bot.handlers.user import handle_start, select_profile_photo
from dzen_frame_bot.image_processing import ProcessedImage
from dzen_frame_bot.keyboards import (
    PROFILE_PHOTO_CALLBACK,
    UPLOAD_PHOTO_CALLBACK,
    main_keyboard,
    repeat_keyboard,
)
from dzen_frame_bot.services.guards import AlbumGuard, UserRequestGuard
from dzen_frame_bot.services.photo_processing import PhotoProcessingService
from dzen_frame_bot.stats import StatsEvent
from dzen_frame_bot.texts import WELCOME_TEXT


class RecordingImageProcessor:
    def __init__(self) -> None:
        self.received: bytes | None = None
        self.max_input_bytes = 123

    def process(self, image_bytes: bytes) -> ProcessedImage:
        self.received = image_bytes
        return ProcessedImage(
            png=b"png",
            jpeg=b"jpeg",
            detected_faces=1,
            used_face_crop=True,
        )


def test_main_keyboard_offers_only_profile_photo_shortcut() -> None:
    callbacks = {
        button.callback_data
        for row in main_keyboard().inline_keyboard
        for button in row
    }

    assert callbacks == {PROFILE_PHOTO_CALLBACK}


def test_start_handler_sends_welcome_and_keyboard() -> None:
    message = AsyncMock()
    stats_service = AsyncMock()

    asyncio.run(handle_start(message, stats_service))

    stats_service.record.assert_awaited_once_with(StatsEvent.START)
    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert args == (WELCOME_TEXT,)
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["reply_markup"] == main_keyboard()


def test_welcome_contains_branded_custom_emoji_ids() -> None:
    assert 'emoji-id="5469683509071205995"' in WELCOME_TEXT
    assert 'emoji-id="5474654521399465276"' in WELCOME_TEXT


def test_repeat_keyboard_keeps_both_photo_sources() -> None:
    callbacks = {
        button.callback_data
        for row in repeat_keyboard().inline_keyboard
        for button in row
    }

    assert callbacks == {UPLOAD_PHOTO_CALLBACK, PROFILE_PHOTO_CALLBACK}


def test_select_profile_photo_returns_largest_size() -> None:
    small = PhotoSize(
        file_id="small",
        file_unique_id="small-unique",
        width=160,
        height=160,
    )
    large = PhotoSize(
        file_id="large",
        file_unique_id="large-unique",
        width=640,
        height=640,
    )

    assert select_profile_photo([[small, large]]) is large
    assert select_profile_photo([]) is None


def test_album_guard_notifies_once_per_group() -> None:
    async def scenario() -> None:
        guard = AlbumGuard()

        assert await guard.should_notify("album-1") is True
        assert await guard.should_notify("album-1") is False
        assert await guard.should_notify("album-2") is True

    asyncio.run(scenario())


def test_user_guard_allows_one_active_operation_per_user() -> None:
    async def scenario() -> None:
        guard = UserRequestGuard()

        assert await guard.try_acquire(1) is True
        assert await guard.try_acquire(1) is False
        assert await guard.try_acquire(2) is True
        await guard.release(1)
        assert await guard.try_acquire(1) is True

    asyncio.run(scenario())


def test_photo_service_processes_bytes_in_async_boundary() -> None:
    processor = RecordingImageProcessor()
    service = PhotoProcessingService(processor)  # type: ignore[arg-type]

    result = asyncio.run(service.process(b"source"))

    assert processor.received == b"source"
    assert service.max_input_bytes == 123
    assert result.png == b"png"
