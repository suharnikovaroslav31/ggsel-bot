from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Router
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import db
from handlers.admin import router as admin_router
from handlers.deals import router as deals_router
from handlers.emoji_tools import router as emoji_router
from handlers.requisites import router as requisites_router
from handlers.start import router as start_router
from utils.media import send_ui


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user and await db.is_banned(user.id):
            if isinstance(event, Message):
                await send_ui(event.bot, event.chat.id, "🚫 Вы заблокированы и не можете пользоваться ботом.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Вы заблокированы", show_alert=True)
            return None
        return await handler(event, data)


def setup_routers() -> Router:
    root = Router()
    root.message.middleware(BanMiddleware())
    root.callback_query.middleware(BanMiddleware())
    root.include_router(start_router)
    root.include_router(admin_router)
    root.include_router(deals_router)
    root.include_router(requisites_router)
    root.include_router(emoji_router)
    return root
