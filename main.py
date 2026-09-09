"""Точка входа для хостинга (Bothost ищет main.py)."""

from bot import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
