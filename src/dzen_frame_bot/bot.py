"""Telegram bot construction and polling startup."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher

from dzen_frame_bot.config import Settings

logger = logging.getLogger(__name__)


def create_dispatcher() -> Dispatcher:
    """Build the root dispatcher used by all feature routers."""
    return Dispatcher()


async def run_bot(settings: Settings) -> None:
    """Run one long-polling process until the application is stopped."""
    dispatcher = create_dispatcher()
    bot = Bot(token=settings.bot_token)

    logger.info("Starting Telegram long polling")
    await dispatcher.start_polling(
        bot,
        allowed_updates=dispatcher.resolve_used_update_types(),
        close_bot_session=True,
    )
