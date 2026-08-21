"""Telegram bot construction and polling startup."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher

from dzen_frame_bot.config import Settings
from dzen_frame_bot.handlers.user import router as user_router
from dzen_frame_bot.image_processing import ImageProcessor
from dzen_frame_bot.mediapipe_detector import MediaPipeFaceDetector
from dzen_frame_bot.resources import FACE_MODEL_PATH, FRAME_PATH
from dzen_frame_bot.services.guards import AlbumGuard, UserRequestGuard
from dzen_frame_bot.services.photo_processing import PhotoProcessingService

logger = logging.getLogger(__name__)


def create_dispatcher(
    photo_service: PhotoProcessingService,
    album_guard: AlbumGuard,
    user_guard: UserRequestGuard,
) -> Dispatcher:
    """Build the root dispatcher used by all feature routers."""
    dispatcher = Dispatcher(
        photo_service=photo_service,
        album_guard=album_guard,
        user_guard=user_guard,
    )
    dispatcher.include_router(user_router)
    return dispatcher


async def run_bot(settings: Settings) -> None:
    """Run one long-polling process until the application is stopped."""
    with MediaPipeFaceDetector(FACE_MODEL_PATH) as detector:
        image_processor = ImageProcessor(detector, FRAME_PATH)
        photo_service = PhotoProcessingService(image_processor)
        dispatcher = create_dispatcher(
            photo_service=photo_service,
            album_guard=AlbumGuard(),
            user_guard=UserRequestGuard(),
        )
        bot = Bot(token=settings.bot_token)

        logger.info("Starting Telegram long polling")
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            close_bot_session=True,
        )
