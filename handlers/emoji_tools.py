"""
Как достать premium emoji ID:
1. /emoji_ids в своём боте
2. Перешли welcome от GGSel
3. Скинь ответ сюда / вставь в config.CUSTOM_EMOJI
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.admin_access import is_admin
from utils.media import reply_ui

router = Router()

# Порядок эмодзи в welcome GGSel
WELCOME_KEYS = [
    "coffee",
    "construction",
    "lightning",
    "one",
    "two",
    "shield",
    "three",
    "trident",
    "four",
    "handshake",
]


def _utf16_slice(text: str, offset: int, length: int) -> str:
    """Telegram entity offset/length считаются в UTF-16 code units."""
    encoded = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    try:
        return encoded[start:end].decode("utf-16-le")
    except Exception:
        return "?"


def _collect_custom(message: Message) -> list:
    entities = list(message.entities or []) + list(message.caption_entities or [])
    return [e for e in entities if e.type == "custom_emoji" and e.custom_emoji_id]


@router.message(Command("emoji_ids"))
async def emoji_ids_help(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        return
    await reply_ui(
        message,
        "Перешли мне <b>welcome</b> от GGSel\n"
        "(сообщение «Добро пожаловать в GGSel»).\n\n"
        "Я верну ID и готовый кусок для <code>config.py</code>.",
    )


@router.message(F.entities | F.caption_entities)
async def extract_custom_emoji(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        return

    custom = _collect_custom(message)
    if not custom:
        return

    text_src = message.text or message.caption or ""
    lines = ["<b>Найденные custom_emoji_id:</b>\n"]
    for i, ent in enumerate(custom, start=1):
        chunk = _utf16_slice(text_src, ent.offset, ent.length) or "?"
        hint = WELCOME_KEYS[i - 1] if i <= len(WELCOME_KEYS) else "btn_?"
        lines.append(
            f"{i}. <code>{ent.custom_emoji_id}</code>  →  {chunk}  "
            f"(если это welcome → <code>{hint}</code>)"
        )

    if len(custom) == len(WELCOME_KEYS):
        lines.append("\n<b>Готово для config.py (если переслал именно welcome):</b>\n")
        lines.append("<pre>")
        for key, ent in zip(WELCOME_KEYS, custom):
            lines.append(f'    "{key}": "{ent.custom_emoji_id}",')
        lines.append("</pre>")
        lines.append("\nСкопируй это и скинь мне — вставлю в код.")
    else:
        lines.append(
            f"\nНайдено {len(custom)} эмодзи, для welcome обычно нужно {len(WELCOME_KEYS)}.\n"
            "Перешли именно стартовое сообщение с картинкой «Добро пожаловать…»."
        )

    await reply_ui(message, "\n".join(lines))
