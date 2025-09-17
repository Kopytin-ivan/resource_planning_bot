# bot/handlers/menu_text.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from ..keyboards.periods import periods_kb
from ..keyboards.units import units_keyboard
from .. import gas_client

router = Router(name="menu_text")

@router.message(F.text == "📊 Общая загруженность")
async def on_all_load_pressed(msg: Message):
    await msg.answer(
        "Выберите период для общей загруженности:",
        reply_markup=periods_kb(scope="load_all")
    )

@router.message(F.text == "🧩 Загруженность юнита")
async def on_unit_load_pressed(msg: Message):
    resp = await gas_client.list_units()
    if not resp.get("ok"):
        await msg.answer(f"Не удалось получить список юнитов: {resp.get('error') or 'неизвестная ошибка'}")
        return
    units = resp.get("units") or []
    tops = [u for u in units if "." not in str(u.get("code", ""))]
    kb = units_keyboard(tops, page=1, action_prefix="unitload_top")
    await msg.answer(hbold("Выберите отдел:"), reply_markup=kb)

@router.message(F.text == "🔚 Завершения")
async def on_endings_pressed(msg: Message):
    # показываем периоды сразу для завершений по всем отделам
    await msg.answer(
        "Показать проекты, которые завершатся…",
        reply_markup=periods_kb(scope="endings__ALL")  # ключевое отличие
    )

