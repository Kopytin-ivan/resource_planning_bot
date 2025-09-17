# bot/handlers/period_select.py
from __future__ import annotations
from datetime import date
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode
import asyncio
from aiogram.enums import ChatAction

from ..keyboards.periods import PeriodCB
from ..utils.date_ranges import period_to_range
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
        scope = (callback_data.scope or "").replace("__", ":")   # "endings__ALL" → "endings:ALL"
        token = callback_data.period or "quarter"

        # 1) Общая загруженность
        if scope == "load_all":
            rng = period_to_range(token) or {}
            try:
                await cb.answer("Готовлю отчёт…", show_alert=False)
            except Exception:
                pass
            resp = await gas_load_all(**rng)
            chunks = resp.get("chunks") or []
            title = hbold("📊 Общая загруженность")
            if not chunks:
                await cb.message.answer(f"{title}\nнет проектов в выбранном периоде")
            else:
                for ch in chunks:
                    for part in split_text(ch, limit=3900):
                        await cb.message.answer(part)
            return

        # 2) Завершения (по всем юнитам или по конкретному)
        if scope.startswith("endings:"):
            code = scope.split(":", 1)[1] if ":" in scope else ""
            unit = None if (not code or code.upper() == "ALL") else code

            # 0) показать «загрузка» и погасить спиннер callback'а
            try:
                await cb.answer("Готовлю список…", show_alert=False)
            except Exception:
                pass
            loading = await cb.message.answer("⏳ Собираю завершения…")

            # 0.1) держим «печатает…» пока грузится
            async def keep_typing():
                try:
                    while True:
                        await cb.message.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
                        await asyncio.sleep(4)
                except asyncio.CancelledError:
                    pass
            typing_task = asyncio.create_task(keep_typing())

            try:
                # 1) дергаем нужный эндпоинт GAS по выбранному периоду
                today = date.today()
                token = callback_data.period or "quarter"
                if token == "this_month":
                    resp = await list_endings_in_month(unit, month=today.month, year=today.year)
                elif token == "next_month":
                    nm, ny = today.month + 1, today.year
                    if nm == 13:
                        nm, ny = 1, ny + 1
                    resp = await list_endings_in_month(unit, month=nm, year=ny)
                elif token == "quarter":
                    resp = await list_endings_within_months(unit, n=3)
                elif token == "half_year":
                    resp = await list_endings_within_months(unit, n=6)
                elif token == "year":
                    resp = await list_endings_within_months(unit, n=12)
                else:
                    resp = await list_endings_within_months(unit, n=3)

                # 2) рендер
                chunks = resp.get("chunks") or []
                parts = []
                for ch in chunks:
                    parts.extend(split_text(ch, limit=3900))

                if not parts:
                    await loading.edit_text("🔚 Завершения\nВ выбранный период завершений не найдено.")
                else:
                    # первый кусок — редактируем «⏳»-сообщение
                    await loading.edit_text(parts[0])
                    # остальные — как новые сообщения
                    for p in parts[1:]:
                        await cb.message.answer(p)
            finally:
                typing_task.cancel()
            return


        # 3) Загрузка конкретного юнита (если где-то используешь periods_kb для него)
        if scope.startswith("load_unit:"):
            unit = scope.split(":", 1)[1]
            rng = period_to_range(token) or {}
            args = {"unit": unit, **rng}
            resp = await gas_load_unit(**args)
            text = resp.get("text") or "Пусто"
            await cb.message.answer(text[:4096])
            try:
                await cb.answer()
            except Exception:
                pass
            return

        # 4) Неизвестный scope
        await cb.message.answer(f"Неизвестный scope: {hcode(scope)}")
        await cb.answer()

    except Exception as e:
        await cb.message.answer(f"⚠️ Ошибка при обработке периода:\n{hcode(str(e))}")
        try:
            await cb.answer()
        except Exception:
            pass
