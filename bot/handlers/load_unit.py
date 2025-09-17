# bot/handlers/load_unit.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hcode

from ..gas_client import load_unit
from ..utils.periods import period_bounds
from ..keyboards.units import units_keyboard  # предполагаю, что у тебя есть клавиатура выбора юнита

router = Router(name="unit_load")

async def _send_unit_load(cb: CallbackQuery, unit: str, period_key: str):
    try:
        dt_from, dt_to = period_bounds(period_key)
        msg = await cb.message.reply(f"⏳ Считаю загруженность для UNIT {unit}…")
        data = await load_unit(**{"unit": unit, "from": dt_from, "to": dt_to})
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or "unknown error")

        text = data.get("text") or "Пусто."
        head = f"📦 UNIT {unit}\nПериод: {dt_from} — {dt_to}\n\n"
        await msg.edit_text((head + text)[:4096])
    except Exception as e:
        await cb.message.answer(f"⚠️ Ошибка при загрузке юнита:\n{hcode(str(e))}")

# 1) Поддержка твоей старой кнопки с callback_data="unit_load" — сначала попросим выбрать юнит
@router.callback_query(F.data == "unit_load")
async def on_unit_load_legacy(cb: CallbackQuery):
    await cb.answer()
    # показываем клавиатуру выбора юнита; по умолчанию далее считаем текущий месяц
    await cb.message.answer("Выбери UNIT:", reply_markup=units_keyboard(prefix="unitload", period="month"))

# 2) Новый формат:
# "unitload:<unit>:month"
# "unitload:<unit>:quarter"
# "unitload:<unit>:year"
# "unitload:<unit>:custom:YYYY-MM-DD:YYYY-MM-DD"
@router.callback_query(F.data.startswith("unitload:"))
async def on_unit_load(cb: CallbackQuery):
    await cb.answer()
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await cb.message.answer("Некорректные параметры для загрузки юнита.")
        return

    unit = parts[1]
    kind = parts[2]
    period_key = kind
    if kind == "custom" and len(parts) >= 5:
        period_key = f"{kind}:{parts[3]}:{parts[4]}"

    await _send_unit_load(cb, unit, period_key)
