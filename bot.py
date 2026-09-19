import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_IDS, BOT_TOKEN, PROXY_URL, SUPER_ADMIN_ID, WEBAPP_URL
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
    admins = set(ADMIN_IDS) | {SUPER_ADMIN_ID}
    logging.info("Owner: %s | Admins: %s", SUPER_ADMIN_ID, ", ".join(str(x) for x in sorted(admins)))
    logging.info("Proxy: %s", PROXY_URL or "(off)")

    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else AiohttpSession()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    await db.connect()
    runner = None
    try:
        try:
            from webapp_server import start_http

            runner = await start_http()
        except Exception as exc:
            logging.exception("HTTP не поднялся, бот всё равно стартует: %s", exc)

        me = None
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

        if runner is not None:
            try:
                from webapp_server import bind_bot_menu as _bind

                await _bind(bot)
            except Exception as exc:
                logging.warning("Mini App menu: %s", exc)

        db_admins = await db.list_admins()
        logging.info("Admins in DB: %s", ", ".join(str(x) for x in db_admins) or "(none)")
        logging.info("Bot started as @%s", me.username if me else "?")
        if WEBAPP_URL:
            logging.info("Mini App: %s", WEBAPP_URL)
        await dp.start_polling(bot)
    finally:
        if runner is not None:
            await runner.cleanup()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
