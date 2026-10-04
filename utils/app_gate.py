from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from database import db
from keyboards.main import open_app_kb
from texts.i18n import welcome_text
from utils.media import edit_ui, reply_ui, send_ui
from config import MANAGER_USERNAME

_RU_LANGS = ("ru", "uk", "be")


def _welcome_text() -> str:
    manager = (MANAGER_USERNAME or "GGsel_Officials").lstrip("@")
    return (
        "👋 Добро пожаловать!\n"
        "\n"
        "<blockquote>💼 GG SELL — надёжный сервис для безопасных сделок!\n"
        "Автоматизировано, быстро и без лишних хлопот!</blockquote>\n"
        "<blockquote>🌚 Комиссия за услугу: всего 1%\n"
        f"⏱ Поддержка 24/7: @{manager}</blockquote>\n"
        "\n"
        "❤️ Теперь ваши сделки под защитой! 🛡️"
    )


def detect_ui_lang(code: str | None) -> str:
    raw = str(code or "").strip().lower().replace("_", "-").split("-")[0]
    return "ru" if raw in _RU_LANGS else "en"


def lang_picked(user) -> bool:
    if not user:
        return False
    try:
        return int(user["lang_picked"] or 0) == 1
    except (KeyError, IndexError, TypeError):
        return False


async def apply_auto_language(tg_user) -> None:
    if tg_user is None:
        return
    user = await db.get_user(tg_user.id)
    if lang_picked(user):
        return
    await db.upsert_user(
        tg_user.id,
        getattr(tg_user, "username", None),
        getattr(tg_user, "full_name", None) or str(tg_user.id),
    )
    await db.set_language(tg_user.id, detect_ui_lang(getattr(tg_user, "language_code", None)))


def entry_text(user) -> str:
    lang = "ru"
    if user:
        try:
            lang = user["language"] or "ru"
        except (KeyError, IndexError, TypeError):
            lang = "ru"
    if str(lang).lower().startswith("en"):
        return welcome_text("en")
    return _welcome_text()


def entry_kb(user, deal: str | None = None) -> InlineKeyboardMarkup:
    return open_app_kb(f"deal={deal}" if deal else "")


async def wipe_reply_kb(bot, chat_id: int) -> None:
    try:
        wipe = await bot.send_message(chat_id, "\u2060", reply_markup=ReplyKeyboardRemove())
        await wipe.delete()
    except Exception:
        pass


async def send_app(
    event: Message | CallbackQuery,
    state: FSMContext | None = None,
    deal: str | None = None,
) -> None:
    if state is not None:
        await state.clear()
    await apply_auto_language(event.from_user)
    user = await db.get_user(event.from_user.id)
    kb = entry_kb(user, deal)
    text = entry_text(user)
    chat_id = event.from_user.id if isinstance(event, CallbackQuery) else event.chat.id
    if isinstance(event, CallbackQuery):
        try:
            await edit_ui(event, text, kb)
        except Exception:
            try:
                await send_ui(event.bot, event.from_user.id, text, kb)
            except Exception:
                pass
        await event.answer()
    else:
        await reply_ui(event, text, kb)
    await wipe_reply_kb(event.bot, chat_id)
