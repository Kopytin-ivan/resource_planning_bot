# bot/handlers/load_all.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

from ..keyboards.periods import periods_kb, PeriodCB
from ..utils.date_ranges import period_to_range
from ..utils.tg_utils import split_text
from ..gas_client import load_all as gas_load_all
from bot.utils.tg_utils import strip_codes_in_text, loading_message, pn, answer_html, edit_html, gas_guard

import re
from ..utils.tg_utils import split_text, strip_codes_in_text, answer_html


router = Router(name="load_all")
_HDR_RE = re.compile(r'(?m)^(?:\s*🧩\s*)?\(UNIT\s*\d+(?:\.\d+)?\).*?$')
_WEEKS_TAIL_RE = re.compile(r'(?m)\s*\(\d+\)\s*$')

def _beautify(text: str) -> str:
    # 1) убираем цифровые префиксы у проектов
    t = strip_codes_in_text(text)
    # 2) делаем жирным строки-заголовки вида "(UNIT X)" и "(UNIT X.Y) ..."
    t = _HDR_RE.sub(lambda m: f"<b>{m.group(0)}</b>", t)
    # 3) убираем в конце строки " (N)" — количество недель
    t = _WEEKS_TAIL_RE.sub('', t)
    return t
@router.callback_query(F.data == "menu:load_all")
@gas_guard()
async def open_periods_menu(cb: CallbackQuery):
    # Просто показываем клавиатуру выбора периода
    await cb.message.edit_text("Выберите период:", reply_markup=periods_kb("load_all"))
    await cb.answer()

@router.callback_query(PeriodCB.filter(F.scope == "load_all"))
@gas_guard()
async def on_period_selected(cb: CallbackQuery, callback_data: PeriodCB):
    period = callback_data.period  # "this_month" | "next_month" | "quarter" | "half_year" | "year" | "none"

    # 1) СРАЗУ подтверждаем клик, чтобы не словить "query is too old"
    try:
        await cb.answer("Готовлю отчёт…", show_alert=False)
    except Exception:
        # если телега уже не ждёт ответа — просто продолжаем
        pass

    # 2) Плейсхолдер, пока грузим отчёт
    wait_msg: Message = await cb.message.answer("⏳ Формирую отчёт…")

    try:
        rng = period_to_range(period)  # -> {"from": "...", "to": "..."} или None
        args = rng or {}

        resp = await gas_load_all(**args)
        if not (resp and resp.get("ok")):
            raise RuntimeError(resp.get("error") or "unknown error")

        # GAS может возвращать заранее разбитые части
        chunks = resp.get("chunks") or []
        title = hbold("Общая загруженность")

        # 3) Удалим плейсхолдер и отправим результат батчами
        try:
            await wait_msg.delete()
        except Exception:
            pass

        if not chunks:
            await cb.message.answer(f"{title}\n\nНет данных за выбранный период.")
        else:
            for chunk in chunks:
                text = f"{title}\n\n{_beautify(chunk)}".strip()
                for part in split_text(text, limit=3900):
                    # HTML-режим, чтобы <b> работал
                    await answer_html(cb, part)


        # 4) Вернём клавиатуру выбора периода
        await cb.message.answer("Выберите период:", reply_markup=periods_kb("load_all"))

    except Exception as e:
        # Если что-то пошло не так — редактируем плейсхолдер или просто шлём сообщение об ошибке
        try:
            await wait_msg.edit_text(f"⚠️ Ошибка при запросе общей загруженности:\n{e}")
        except Exception:
            await cb.message.answer(f"⚠️ Ошибка при запросе общей загруженности:\n{e}")
