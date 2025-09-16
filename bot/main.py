import asyncio
import os
import ssl

# ⚠️ DEV-КОСТЫЛЬ: полностью выключаем проверку SSL в процессе
# делаем это ДО любых сетевых импортов/созданий клиентов
ssl._create_default_https_context = ssl._create_unverified_context
ssl.create_default_context = ssl._create_unverified_context

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .handlers.start import router as start_router
from .handlers.load_all import router as load_all_router
from .handlers.load_unit import router as load_unit_router


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    bot = Bot(token=token)                  # обычная сессия, без кастомного connector
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(load_all_router)
    dp.include_router(load_unit_router)

    print("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
