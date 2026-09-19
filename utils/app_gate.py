from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from database import db
from keyboards.main import language_start_kb, open_app_kb
from utils.media import edit_ui, reply_ui, send_ui

APP_PROMPT = "Выберите язык / Choose language"
APP_READY = "Откройте GGSel / Open GGSel"


def lang_picked(user) -> bool:
    if not user:
        return False
    try:
        return int(user["lang_picked"] or 0) == 1
    except (KeyError, IndexError, TypeError):
        return False


def entry_text(user) -> str:
    return APP_READY if lang_picked(user) else APP_PROMPT


def entry_kb(user, deal: str | None = None) -> InlineKeyboardMarkup:
    if lang_picked(user):
        return open_app_kb(f"deal={deal}" if deal else "")
    return language_start_kb(deal)


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
