# bot/handlers/menu_text.py
from aiogram import Router, F
from aiogram.types import Message

from ..keyboards.periods import periods_kb
from ..keyboards.units import units_keyboard  # твой уже существующий генератор списка юнитов

router = Router(name="menu_text")

@router.message(F.text == "📊 Общая загруженность")
async def on_all_load_pressed(msg: Message):
    await msg.answer(
        "Выберите период для общей загруженности:",
        reply_markup=periods_kb(scope="load_all")
    )

@router.message(F.text == "🧩 Загруженность юнита")
async def on_unit_load_pressed(msg: Message):
    # 1-й шаг: показать юниты (inline)
    await msg.answer(
        "Выберите юнит:",
        reply_markup=await units_keyboard()  # если async; иначе без await
    )

@router.message(F.text == "🔚 Завершения")
async def on_endings_pressed(msg: Message):
    # при желании — тоже через периоды
    await msg.answer(
        "Выберите период для списка завершений:",
        reply_markup=periods_kb(scope="load_all")  # можно сделать отдельный scope, если логика иная
    )

@router.message(F.text == "➕ Добавить проект")
async def on_add_project_pressed(msg: Message):
    # здесь можно показать inline-форму/серии шагов: выбрать юнит → ввести поля → подтвердить
    await msg.answer("Ок, выберите юнит для добавления проекта:", reply_markup=await units_keyboard())

@router.message(F.text == "⚙️ Ещё")
async def on_more_pressed(msg: Message):
    await msg.answer("Доступны действия: пометить статус, продлить срок, перенести проект и т.д.")
