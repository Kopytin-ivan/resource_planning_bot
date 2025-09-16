# bot/handlers/load_all.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from ..keyboards.periods import periods_keyboard
from ..utils.date_ranges import preset_range
from ..gas_client import get_all_load
from ..utils.tg_utils import reply_long   # см. шаг 5

router = Router()

@router.callback_query(F.data == "all_load")
async def pick_period(cb: CallbackQuery):
    await cb.message.edit_text("Выбери период:", reply_markup=periods_keyboard("allload"))
    await cb.answer()

@router.callback_query(F.data.startswith("allload:preset:"))
async def run_all(cb: CallbackQuery):
    _, _, preset = cb.data.split(":")
    dt_from, dt_to = (None, None) if preset == "none" else preset_range(preset)
    r = await get_all_load(dt_from, dt_to)
    chunks = r.get("chunks") or []
    if not chunks:
        await cb.message.edit_text("Пусто по заданному периоду.", reply_markup=periods_keyboard("allload"))
    else:
        await cb.message.edit_text("Готово. Отправляю…")
        for block in chunks:
            await reply_long(cb.message.bot, cb.message.chat.id, block)
    await cb.answer()
