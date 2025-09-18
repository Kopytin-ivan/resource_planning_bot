import asyncio
import os
import ssl
import logging

# ⚠️ Только для разработки — отключаем проверку SSL
ssl._create_default_https_context = ssl._create_unverified_context
ssl.create_default_context = ssl._create_unverified_context

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from .handlers.edit_dates import router as edit_dates_router
from .handlers.add_project import router as add_project_router
from .handlers.period_select import router as period_select_router 
from .handlers.add_project import router as add_project_router 
from .handlers.start import router as start_router, setup_bot_commands
from .handlers.menu_text import router as menu_text_router
from .handlers.load_all import router as load_all_router       
from .handlers.load_unit import router as unit_load_router
from .handlers.change_manager import router as change_manager_router
from .handlers.status_lists import router as status_lists_router
from .handlers.remove_project import router as remove_project_router
from .handlers.overall import router as overall_router
from .handlers.debug import router as debug_router             # оставляем САМЫМ ПОСЛЕДНИМ

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: специфичные роутеры → в самом конце «всеядный» debug
    dp.include_router(start_router)
    dp.include_router(menu_text_router)
    dp.include_router(load_all_router)   # ⬅ теперь хендлер периодов для «Общей загруженности» реально работает
    dp.include_router(add_project_router)
    dp.include_router(period_select_router)
    dp.include_router(edit_dates_router) 
    dp.include_router(unit_load_router)
    dp.include_router(change_manager_router)
    dp.include_router(status_lists_router)
    dp.include_router(remove_project_router)
    dp.include_router(overall_router)
    dp.include_router(debug_router)      # ⬅ самый последний

    await setup_bot_commands(bot)
    print("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
