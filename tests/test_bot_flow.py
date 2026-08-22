"""Tests for Telegram flow helpers and short-lived guards."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.types import PhotoSize

from dzen_frame_bot.handlers.user import (
    PHOTO_REACTION_EMOJI,
    _react_to_uploaded_photo,
    handle_start,
    select_profile_photo,
)
from dzen_frame_bot.image_processing import ProcessedImage
from dzen_frame_bot.keyboards import (
    PROFILE_PHOTO_CALLBACK,
    UPLOAD_PHOTO_CALLBACK,
    alternative_photo_keyboard,
    main_keyboard,
    photo_source_keyboard,
    repeat_keyboard,
    upload_photo_keyboard,
)
from dzen_frame_bot.services.guards import AlbumGuard, UserRequestGuard
from dzen_frame_bot.services.photo_processing import PhotoProcessingService
from dzen_frame_bot.stats import StatsEvent
from dzen_frame_bot.texts import (
    BUSY_TEXT,
    GENERIC_ERROR_TEXT,
    INVALID_IMAGE_TEXT,
    NO_PROFILE_PHOTO_TEXT,
    RESULT_DOCUMENT_TEXT,
    TOO_LARGE_TEXT,
    WELCOME_TEXT,
)


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


def test_directly_uploaded_photo_gets_heart_on_fire_reaction() -> None:
    message = SimpleNamespace(chat=SimpleNamespace(id=10), message_id=20)
    bot = AsyncMock()

    asyncio.run(_react_to_uploaded_photo(message, bot))

    bot.set_message_reaction.assert_awaited_once()
    kwargs = bot.set_message_reaction.await_args.kwargs
    assert kwargs["chat_id"] == 10
    assert kwargs["message_id"] == 20
    assert len(kwargs["reaction"]) == 1
    assert kwargs["reaction"][0].emoji == PHOTO_REACTION_EMOJI


def test_repeat_keyboard_keeps_both_photo_sources() -> None:
    buttons = {
        button.callback_data: button.text
        for row in repeat_keyboard().inline_keyboard
        for button in row
    }

    assert buttons == {
        UPLOAD_PHOTO_CALLBACK: "Сделать еще фото",
        PROFILE_PHOTO_CALLBACK: "Использовать фото профиля",
    }


def test_error_keyboards_offer_requested_photo_sources() -> None:
    source_buttons = {
        button.callback_data: button.text
        for row in photo_source_keyboard().inline_keyboard
        for button in row
    }
    alternative_buttons = {
        button.callback_data: button.text
        for row in alternative_photo_keyboard().inline_keyboard
        for button in row
    }
    upload_buttons = {
        button.callback_data: button.text
        for row in upload_photo_keyboard().inline_keyboard
        for button in row
    }

    assert source_buttons == {
        UPLOAD_PHOTO_CALLBACK: "Загрузить фото",
        PROFILE_PHOTO_CALLBACK: "Использовать фото профиля",
    }
    assert alternative_buttons == {
        UPLOAD_PHOTO_CALLBACK: "Выбрать другое фото",
        PROFILE_PHOTO_CALLBACK: "Использовать фото профиля",
    }
    assert upload_buttons == {UPLOAD_PHOTO_CALLBACK: "Загрузить фото"}


def test_error_and_document_texts_contain_custom_emoji_ids() -> None:
    down_emoji_id = 'emoji-id="5474654521399465276"'

    assert down_emoji_id in NO_PROFILE_PHOTO_TEXT
    assert down_emoji_id in TOO_LARGE_TEXT
    assert down_emoji_id in INVALID_IMAGE_TEXT
    assert 'emoji-id="5472111647357162128"' in BUSY_TEXT
    assert 'emoji-id="5474615892463606245"' in GENERIC_ERROR_TEXT
    assert 'emoji-id="5258301191745459772"' in RESULT_DOCUMENT_TEXT


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
