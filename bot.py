import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_IDS, BOT_TOKEN, PROXY_URL
from database import db
from handlers import setup_routers


async def main() -> None:
    if not BOT_TOKEN:
        logging.error("Укажи BOT_TOKEN в файле .env")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if not ADMIN_IDS:
        logging.warning("ADMIN_IDS пуст — /admin не будет работать")
    else:
        logging.info("Admins: %s", ", ".join(str(x) for x in sorted(ADMIN_IDS)))

    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else AiohttpSession()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    await db.connect()
    try:
        for attempt in range(1, 11):
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                me = await bot.get_me()
                break
            except Exception as exc:
                logging.warning("Connect attempt %s/10 failed: %s", attempt, exc)
                if attempt == 10:
                    raise
                await asyncio.sleep(3)
        db_admins = await db.list_admins()
        logging.info("Admins in DB: %s", ", ".join(str(x) for x in db_admins) or "(none)")
        logging.info("Bot started as @%s", me.username)
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
