"""Хелперы для Telegram premium / custom emoji."""

from __future__ import annotations

from config import CUSTOM_EMOJI


def ce(key: str, fallback: str) -> str:
    """HTML-тег custom emoji или обычный фолбэк."""
    emoji_id = (CUSTOM_EMOJI.get(key) or "").strip()
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def icon_id(key: str) -> str | None:
    """icon_custom_emoji_id для InlineKeyboardButton."""
    value = (CUSTOM_EMOJI.get(key) or "").strip()
    return value or None
