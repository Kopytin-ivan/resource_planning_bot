# bot/handlers/load_unit.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from ..keyboards.units import units_keyboard
from ..keyboards.periods import periods_keyboard
from ..utils.date_ranges import preset_range
from ..gas_client import list_units_and_managers, get_unit_load
from ..utils.tg_utils import reply_long

router = Router()
_UNITS: list[dict] | None = None

async def _get_units():
    global _UNITS
    if _UNITS is None:
        data = await list_units_and_managers()
        _UNITS = data.get("units", [])
    return _UNITS

@router.callback_query(F.data == "unit_load")
async def pick_unit(cb: CallbackQuery):
    units = await _get_units()
    await cb.message.edit_text("Выбери юнит:", reply_markup=units_keyboard(units, page=1, action_prefix="unitload"))
    await cb.answer()

@router.callback_query(F.data.startswith("unitload:page:"))
async def units_page(cb: CallbackQuery):
    units = await _get_units()
    p = int(cb.data.split(":")[-1])
    await cb.message.edit_reply_markup(reply_markup=units_keyboard(units, page=p, action_prefix="unitload"))
    await cb.answer()

@router.callback_query(F.data.startswith("unitload:pick:"))
async def unit_picked(cb: CallbackQuery):
    unit = cb.data.split(":")[-1]
    await cb.message.edit_text(f"UNIT {unit}. Выбери период:", reply_markup=periods_keyboard(f"unitloadrun:{unit}"))
    await cb.answer()

@router.callback_query(F.data.startswith("unitloadrun:"))
async def unit_run(cb: CallbackQuery):
    _, unit, _, preset = cb.data.split(":")
    dt_from, dt_to = (None, None) if preset == "none" else preset_range(preset)
    r = await get_unit_load(unit, dt_from, dt_to)
    text = r.get("text")
    chunks = r.get("chunks")
    await cb.message.edit_text("Готово. Отправляю…")
    if text:
        await reply_long(cb.message.bot, cb.message.chat.id, text)
    if chunks:
        for block in chunks:
            await reply_long(cb.message.bot, cb.message.chat.id, block)
    await cb.answer()
