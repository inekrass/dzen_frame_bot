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
