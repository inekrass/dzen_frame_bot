"""Administrative Telegram commands."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from dzen_frame_bot.stats import StatsCounters, StatsService, StatsSnapshot
from dzen_frame_bot.texts import ACCESS_DENIED_TEXT, STATS_ERROR_TEXT

logger = logging.getLogger(__name__)
router = Router(name="admin")


@router.message(Command("myid"))
async def handle_my_id(message: Message) -> None:
    """Show a user their own Telegram ID without storing it."""
    if message.from_user is None:
        return
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")


@router.message(Command("stats"))
async def handle_stats(
    message: Message,
    stats_service: StatsService,
    admin_ids: frozenset[int],
) -> None:
    """Show aggregate statistics only to configured administrators."""
    if message.from_user is None or message.from_user.id not in admin_ids:
        await message.answer(ACCESS_DENIED_TEXT)
        return

    try:
        snapshot = await stats_service.snapshot()
    except Exception:
        logger.exception("Statistics read failed")
        await message.answer(STATS_ERROR_TEXT)
        return
    await message.answer(format_stats(snapshot))


def format_stats(snapshot: StatsSnapshot) -> str:
    """Render a compact Russian-language aggregate report."""
    return (
        f"Статистика за {snapshot.day.strftime('%d.%m.%Y')}\n\n"
        f"Сегодня:\n{_format_counters(snapshot.today)}\n\n"
        f"За всё время:\n{_format_counters(snapshot.total)}"
    )


def _format_counters(counters: StatsCounters) -> str:
    return (
        f"• Запуски: {counters.starts}\n"
        f"• Загруженные фото: {counters.upload_requests}\n"
        f"• Фото профиля: {counters.profile_requests}\n"
        f"• Готовые результаты: {counters.processed}\n"
        f"• Кадрирование по центру: {counters.centered}\n"
        f"• Ошибки: {counters.errors}"
    )
