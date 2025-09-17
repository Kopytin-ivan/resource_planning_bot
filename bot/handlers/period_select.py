# bot/handlers/period_select.py
from __future__ import annotations

from datetime import date
from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode

from ..keyboards.periods import PeriodCB, periods_kb
from ..utils.date_ranges import period_to_range  # если используешь для load_all / load_unit
from ..utils.tg_utils import split_text
from ..gas_client import (
    load_all as gas_load_all,
    load_unit as gas_load_unit,
    list_endings_in_month,
    list_endings_within_months,
)

router = Router(name="period_select")


@router.callback_query(PeriodCB.filter())
async def on_period_selected(cb: CallbackQuery, callback_data: PeriodCB):
    try:
        # 0) Распаковка
        scope = (callback_data.scope or "").replace("__", ":")
        token = callback_data.period or "quarter"

        # 1) Общая загруженность (если жмёшь из меню «Общая загруженность»)
        if scope == "load_all":
            try:
                await cb.answer("Готовлю отчёт…", show_alert=False)
            except Exception:
                pass

            rng = period_to_range(token) or {}
            resp = await gas_load_all(**rng)
            chunks = resp.get("chunks") or []
            title = hbold("Общая загруженность")

            if not chunks:
                await cb.message.answer(f"{title}\n\nНет данных за выбранный период.")
            else:
                for chunk in chunks:
                    text = f"{title}\n\n{chunk}".strip()
                    for part in split_text(text, limit=3900):
                        await cb.message.answer(part)
            return

        # 2) Загрузка конкретного юнита (если где-то используешь с периодом)
        if scope.startswith("load_unit:"):
            unit = scope.split(":", 1)[1]
            try:
                await cb.answer()
            except Exception:
                pass

            rng = period_to_range(token) or {}
            args = {"unit": unit, **rng}
            resp = await gas_load_unit(**args)
            text = resp.get("text") or "Пусто"
            await cb.message.answer(text[:4096])
            return

        # 3) НОВОЕ: Завершения проектов выбранного юнита
        if scope.startswith("endings:"):
            unit = scope.split(":", 1)[1]
            try:
                await cb.answer()
            except Exception:
                pass

            today = date.today()
            m, y = today.month, today.year

            if token == "this_month":
                resp = await list_endings_in_month(unit, month=m, year=y)
            elif token == "next_month":
                m2, y2 = (1, y + 1) if m == 12 else (m + 1, y)
                resp = await list_endings_in_month(unit, month=m2, year=y2)
            elif token == "quarter":
                resp = await list_endings_within_months(unit, n=3)
            elif token == "half_year":
                resp = await list_endings_within_months(unit, n=6)
            elif token == "year":
                resp = await list_endings_within_months(unit, n=12)
            else:
                resp = {"ok": False, "error": f"Unknown period token: {token}"}

            if not resp or not resp.get("ok"):
                err = (resp or {}).get("error") or "ошибка на стороне GAS"
                await cb.message.answer(f"⚠️ Ошибка при запросе завершений: {hcode(err)}")
                return

            chunks = resp.get("chunks") or []
            if not chunks:
                await cb.message.answer("🔚 Завершений не найдено.")
            else:
                for ch in chunks:
                    for part in split_text(ch, limit=3900):
                        await cb.message.answer(part)
            return

        # 4) Фолбэк: неизвестный scope
        await cb.message.answer(f"Неизвестный scope: {hcode(scope)}")

    except Exception as e:
        await cb.message.answer(f"⚠️ Ошибка при обработке периода:\n{hcode(str(e))}")
