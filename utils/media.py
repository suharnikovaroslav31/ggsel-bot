from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

from config import ASSETS_DIR

_CANDIDATES = (
    ASSETS_DIR / "banner.mp4",
    ASSETS_DIR / "banner.gif",
)
_cached_file_id: str | None = None


def animation_source() -> FSInputFile | str | None:
    if _cached_file_id:
        return _cached_file_id
    for path in _CANDIDATES:
        if path.is_file():
            return FSInputFile(path)
    return None


def _has_media(msg: Message | None) -> bool:
    if not msg:
        return False
    return bool(msg.animation or msg.video or msg.photo or msg.document)


async def send_ui(
    bot: Bot,
    chat_id: int | str,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> Message:
    global _cached_file_id
    media = animation_source()
    if media is None:
        return await bot.send_message(chat_id, text, reply_markup=markup)

    sent = await bot.send_animation(
        chat_id,
        animation=media,
        caption=text,
        reply_markup=markup,
    )
    if sent.animation and not _cached_file_id:
        _cached_file_id = sent.animation.file_id
    return sent


async def reply_ui(
    message: Message,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> Message:
    return await send_ui(message.bot, message.chat.id, text, markup)


async def edit_message_ui(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        await bot.edit_message_caption(
            chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup
        )
        return
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
    except Exception:
        pass
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup
        )
        return
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
    except Exception:
        pass
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=markup
        )
    except Exception:
        pass


async def edit_ui(
    callback: CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    msg = callback.message
    if msg and _has_media(msg):
        try:
            await msg.edit_caption(caption=text, reply_markup=markup)
            return msg
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return msg
    elif msg and msg.text:
        try:
            await msg.delete()
        except Exception:
            pass
    if not msg:
        return None
    return await send_ui(callback.bot, msg.chat.id, text, markup)
