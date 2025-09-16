# bot/handlers/start.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from ..keyboards.main_menu import main_menu  # ← относительный импорт

router = Router()

@router.message(F.text.regexp(r"^/(start|help)$"))
async def cmd_start(m: Message):
    await m.answer("Привет! Что делаем?", reply_markup=main_menu())

@router.callback_query(F.data == "home")
async def cb_home(cb: CallbackQuery):
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu())
    await cb.answer()

@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    await cb.message.edit_text(
        "Я бот планирования ресурсов.\n"
        "• 📊 Общая загруженность — суммарно по всем юнитам\n"
        "• 🧩 Загрузка юнита — выбрать UNIT и период",
        reply_markup=main_menu()
    )
    await cb.answer()
