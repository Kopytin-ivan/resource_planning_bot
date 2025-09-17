# bot/handlers/start.py
from aiogram import Router, F
from aiogram.types import Message, BotCommand
from ..keyboards.main_menu import main_menu_kb

router = Router(name="start")

@router.message(F.text == "/start")
async def cmd_start(msg: Message):
    await msg.answer(
        "Привет! Я бот для планирования ресурсов. Выбирай действие ниже 👇",
        reply_markup=main_menu_kb()
    )

@router.message(F.text == "/menu")
async def cmd_menu(msg: Message):
    await msg.answer(
        "Главное меню:",
        reply_markup=main_menu_kb()
    )

# (необязательно) зарегистрируем видимые команды в меню Telegram
async def setup_bot_commands(bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Показать меню"),
        BotCommand(command="menu",  description="Главное меню"),
    ])
