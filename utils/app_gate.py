from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from keyboards.main import language_start_kb
from utils.media import edit_ui, reply_ui, send_ui

APP_PROMPT = "Выберите язык / Choose language"


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
    kb = language_start_kb(deal)
    chat_id = event.from_user.id if isinstance(event, CallbackQuery) else event.chat.id
    if isinstance(event, CallbackQuery):
        try:
            await edit_ui(event, APP_PROMPT, kb)
        except Exception:
            try:
                await send_ui(event.bot, event.from_user.id, APP_PROMPT, kb)
            except Exception:
                pass
        await event.answer()
    else:
        await reply_ui(event, APP_PROMPT, kb)
    await wipe_reply_kb(event.bot, chat_id)
