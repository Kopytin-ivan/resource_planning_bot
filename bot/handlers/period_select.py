# bot/handlers/period_select.py
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hcode

from ..keyboards.periods import PeriodCB
from ..utils.periods import period_bounds_from_token
from ..utils.tg_utils import split_text
from .. import gas_client

router = Router(name="period_select")

@router.callback_query(PeriodCB.filter())
async def on_period_selected(call: CallbackQuery, callback_data: PeriodCB):
    # Подтверждаем клик сразу
    try:
        await call.answer()
    except Exception:
        pass

    scope = callback_data.scope  # "load_all" / "load_unit:<code>"
    period_token = callback_data.period  # "this_month" | "next_month" | "quarter" | ... | "none"
    dt_from, dt_to = period_bounds_from_token(period_token)

    try:
        if scope == "load_all":
            args = {}
            if dt_from and dt_to:
                args = {"from": dt_from, "to": dt_to}
            resp = await gas_client.load_all(**args)
            if not resp.get("ok"):
                raise RuntimeError(resp.get("error") or "Неизвестная ошибка")
            chunks = resp.get("chunks") or [resp.get("text", "Пусто")]
            for block in chunks:
                for part in split_text(block, limit=3900):
                    await call.message.answer(part)
            return

        if scope.startswith("load_unit:"):
            unit = scope.split(":", 1)[1]
            args = {"unit": unit}
            if dt_from and dt_to:
                args["from"] = dt_from
                args["to"] = dt_to
            resp = await gas_client.load_unit(**args)
            if not resp.get("ok"):
                raise RuntimeError(resp.get("error") or "Неизвестная ошибка")
            chunks = resp.get("chunks") or [resp.get("text", "Пусто")]
            for block in chunks:
                for part in split_text(block, limit=3900):
                    await call.message.answer(part)
            return

        await call.message.answer("Неизвестный scope.")
    except Exception as e:
        await call.message.answer(f"⚠️ Ошибка при расчёте периода:\n{hcode(str(e))}")
