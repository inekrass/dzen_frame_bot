"""User-facing Telegram handlers for the photo framing flow."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Document,
    Message,
    PhotoSize,
)
from aiogram.utils.chat_action import ChatActionSender

from dzen_frame_bot.image_processing import ImageTooLargeError, InvalidImageError
from dzen_frame_bot.keyboards import (
    PROFILE_PHOTO_CALLBACK,
    UPLOAD_PHOTO_CALLBACK,
    main_keyboard,
    repeat_keyboard,
)
from dzen_frame_bot.services.guards import AlbumGuard, UserRequestGuard
from dzen_frame_bot.services.photo_processing import PhotoProcessingService
from dzen_frame_bot.stats import StatsEvent, StatsService
from dzen_frame_bot.texts import (
    ALBUM_REJECTED_TEXT,
    BUSY_TEXT,
    GENERIC_ERROR_TEXT,
    INVALID_IMAGE_TEXT,
    NO_PROFILE_PHOTO_TEXT,
    PHOTO_PROMPT_TEXT,
    RESULT_CENTERED_TEXT,
    RESULT_DOCUMENT_TEXT,
    RESULT_READY_TEXT,
    TOO_LARGE_TEXT,
    UNSUPPORTED_MESSAGE_TEXT,
    WELCOME_TEXT,
)

logger = logging.getLogger(__name__)
router = Router(name="user")

SUPPORTED_DOCUMENT_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)


@router.message(CommandStart())
async def handle_start(message: Message, stats_service: StatsService) -> None:
    """Explain the bot and present the two supported photo sources."""
    await stats_service.record(StatsEvent.START)
    await message.answer(WELCOME_TEXT, reply_markup=main_keyboard())


@router.callback_query(F.data == UPLOAD_PHOTO_CALLBACK)
async def handle_upload_choice(callback: CallbackQuery) -> None:
    """Ask the user to send exactly one photo in a separate message."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(PHOTO_PROMPT_TEXT)


@router.callback_query(F.data == PROFILE_PHOTO_CALLBACK)
async def handle_profile_choice(
    callback: CallbackQuery,
    bot: Bot,
    photo_service: PhotoProcessingService,
    user_guard: UserRequestGuard,
    stats_service: StatsService,
) -> None:
    """Download and process the latest available Telegram profile photo."""
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await stats_service.record(StatsEvent.PROFILE_REQUEST)

    try:
        profile_photos = await bot.get_user_profile_photos(
            user_id=callback.from_user.id,
            offset=0,
            limit=1,
        )
    except Exception:
        logger.exception("Profile photo request failed")
        await stats_service.record(StatsEvent.ERROR)
        await callback.message.answer(
            GENERIC_ERROR_TEXT,
            reply_markup=main_keyboard(),
        )
        return
    photo = select_profile_photo(profile_photos.photos)
    if photo is None:
        await callback.message.answer(
            NO_PROFILE_PHOTO_TEXT,
            reply_markup=main_keyboard(),
        )
        return

    await _process_downloadable(
        message=callback.message,
        bot=bot,
        downloadable=photo,
        file_size=photo.file_size,
        user_id=callback.from_user.id,
        photo_service=photo_service,
        user_guard=user_guard,
        stats_service=stats_service,
    )


@router.message(F.photo)
async def handle_uploaded_photo(
    message: Message,
    bot: Bot,
    photo_service: PhotoProcessingService,
    album_guard: AlbumGuard,
    user_guard: UserRequestGuard,
    stats_service: StatsService,
) -> None:
    """Process the largest Telegram representation of one uploaded photo."""
    if await _reject_album(message, album_guard):
        return
    if not message.photo or not message.from_user:
        await message.answer(UNSUPPORTED_MESSAGE_TEXT)
        return

    photo = message.photo[-1]
    await stats_service.record(StatsEvent.UPLOAD_REQUEST)
    await _process_downloadable(
        message=message,
        bot=bot,
        downloadable=photo,
        file_size=photo.file_size,
        user_id=message.from_user.id,
        photo_service=photo_service,
        user_guard=user_guard,
        stats_service=stats_service,
    )


@router.message(F.document)
async def handle_uploaded_document(
    message: Message,
    bot: Bot,
    photo_service: PhotoProcessingService,
    album_guard: AlbumGuard,
    user_guard: UserRequestGuard,
    stats_service: StatsService,
) -> None:
    """Accept a supported image sent as an uncompressed Telegram document."""
    if await _reject_album(message, album_guard):
        return
    document = message.document
    if (
        document is None
        or document.mime_type not in SUPPORTED_DOCUMENT_MIME_TYPES
        or message.from_user is None
    ):
        await message.answer(INVALID_IMAGE_TEXT)
        return

    await stats_service.record(StatsEvent.UPLOAD_REQUEST)
    await _process_downloadable(
        message=message,
        bot=bot,
        downloadable=document,
        file_size=document.file_size,
        user_id=message.from_user.id,
        photo_service=photo_service,
        user_guard=user_guard,
        stats_service=stats_service,
    )


@router.message()
async def handle_unsupported_message(message: Message) -> None:
    """Guide users who send text, video or other unsupported messages."""
    await message.answer(UNSUPPORTED_MESSAGE_TEXT, reply_markup=main_keyboard())


def select_profile_photo(
    photo_groups: list[list[PhotoSize]],
) -> PhotoSize | None:
    """Return the largest size of the latest available profile photo."""
    if not photo_groups or not photo_groups[0]:
        return None
    return max(photo_groups[0], key=lambda photo: photo.width * photo.height)


async def _reject_album(message: Message, album_guard: AlbumGuard) -> bool:
    media_group_id = message.media_group_id
    if media_group_id is None:
        return False
    if await album_guard.should_notify(media_group_id):
        await message.answer(ALBUM_REJECTED_TEXT)
    return True


async def _process_downloadable(
    *,
    message: Message,
    bot: Bot,
    downloadable: PhotoSize | Document,
    file_size: int | None,
    user_id: int,
    photo_service: PhotoProcessingService,
    user_guard: UserRequestGuard,
    stats_service: StatsService,
) -> None:
    if file_size is not None and file_size > photo_service.max_input_bytes:
        await stats_service.record(StatsEvent.ERROR)
        await message.answer(TOO_LARGE_TEXT)
        return
    if not await user_guard.try_acquire(user_id):
        await message.answer(BUSY_TEXT)
        return

    try:
        async with ChatActionSender.upload_photo(chat_id=message.chat.id, bot=bot):
            stream = await bot.download(downloadable, destination=BytesIO())
            if stream is None:
                raise RuntimeError("Telegram returned no downloaded file")
            result = await photo_service.process(stream.read())

        result_caption = (
            RESULT_READY_TEXT if result.used_face_crop else RESULT_CENTERED_TEXT
        )
        await message.answer_photo(
            BufferedInputFile(result.jpeg, filename="dzen-ludi-slova.jpg"),
            caption=result_caption,
        )
        await message.answer_document(
            BufferedInputFile(result.png, filename="dzen-ludi-slova.png"),
            caption=RESULT_DOCUMENT_TEXT,
            reply_markup=repeat_keyboard(),
        )
        await stats_service.record(StatsEvent.PROCESSED)
        if not result.used_face_crop:
            await stats_service.record(StatsEvent.CENTERED)
    except ImageTooLargeError:
        await stats_service.record(StatsEvent.ERROR)
        await message.answer(TOO_LARGE_TEXT)
    except InvalidImageError:
        await stats_service.record(StatsEvent.ERROR)
        await message.answer(INVALID_IMAGE_TEXT)
    except Exception:
        logger.exception("Photo processing failed")
        await stats_service.record(StatsEvent.ERROR)
        await message.answer(GENERIC_ERROR_TEXT, reply_markup=main_keyboard())
    finally:
        await user_guard.release(user_id)
