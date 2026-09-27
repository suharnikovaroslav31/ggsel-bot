"""Локальный запуск Mini App: http://127.0.0.1:3000"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("GGSEL_LOCAL", "1")
os.environ.setdefault("WEB_PORT", "3000")
os.environ.setdefault("PORT", "3000")

from database import db
from webapp_server import start_http


async def main() -> None:
    await db.connect()
    await start_http()
    print("GGSel Mini App: http://127.0.0.1:3000", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
