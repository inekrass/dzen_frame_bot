"""Inline keyboards used by the user photo flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

UPLOAD_PHOTO_CALLBACK = "photo:upload"
PROFILE_PHOTO_CALLBACK = "photo:profile"


def main_keyboard() -> InlineKeyboardMarkup:
    """Offer the Telegram profile photo shortcut after onboarding."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Использовать фото профиля",
                    callback_data=PROFILE_PHOTO_CALLBACK,
                )
            ],
        ]
    )


def photo_source_keyboard() -> InlineKeyboardMarkup:
    """Offer a fresh upload or the Telegram profile photo."""
    return _photo_source_keyboard(upload_text="Загрузить фото")


def alternative_photo_keyboard() -> InlineKeyboardMarkup:
    """Offer another upload after an invalid or oversized image."""
    return _photo_source_keyboard(upload_text="Выбрать другое фото")


def upload_photo_keyboard() -> InlineKeyboardMarkup:
    """Offer a manual upload when the profile photo is unavailable."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Загрузить фото",
                    callback_data=UPLOAD_PHOTO_CALLBACK,
                )
            ]
        ]
    )


def _photo_source_keyboard(*, upload_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=upload_text,
                    callback_data=UPLOAD_PHOTO_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Использовать фото профиля",
                    callback_data=PROFILE_PHOTO_CALLBACK,
                )
            ],
        ]
    )


def repeat_keyboard() -> InlineKeyboardMarkup:
    """Offer the same source choices after a successful result."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сделать еще фото",
                    callback_data=UPLOAD_PHOTO_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Использовать фото профиля",
                    callback_data=PROFILE_PHOTO_CALLBACK,
                )
            ],
        ]
    )
