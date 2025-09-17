# bot/handlers/overall.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hcode

from ..gas_client import load_all
from ..utils.periods import period_bounds

router = Router(name="overall")

async def _send_overall_for_period(target: CallbackQuery | Message, period_key: str):
    try:
        dt_from, dt_to = period_bounds(period_key)
        # сервисное сообщение «думаю…»
        if isinstance(target, CallbackQuery):
            msg = await target.message.reply("⏳ Считаю общую загруженность…")
        else:
            msg = await target.reply("⏳ Считаю общую загруженность…")

        data = await load_all(**{"from": dt_from, "to": dt_to})
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or "unknown error")

        chunks = data.get("chunks") or []
        text = f"📊 Период: {dt_from} — {dt_to}\n\n" + "\n\n".join(chunks) if chunks else f"Данных нет за период {dt_from} — {dt_to}."
        await msg.edit_text(text[:4096])
    except Exception as e:
        err = f"⚠️ Ошибка при запросе общей загруженности:\n{hcode(str(e))}"
        if isinstance(target, CallbackQuery):
            await target.message.answer(err)
        else:
            await target.answer(err)

# 1) Поддержка твоей старой кнопки с callback_data="all_load"
@router.callback_query(F.data == "all_load")
async def on_all_load_legacy(cb: CallbackQuery):
    # обязательно отвечаем, чтобы убрать «часики»
    await cb.answer()
    # по умолчанию считаем ТЕКУЩИЙ МЕСЯЦ
    await _send_overall_for_period(cb, "month")

# 2) Новый формат: overall:month / overall:quarter / overall:year / overall:custom:YYYY-MM-DD:YYYY-MM-DD
@router.callback_query(F.data.startswith("overall:"))
async def on_overall(cb: CallbackQuery):
    await cb.answer()
    try:
        # overall:month
        # overall:quarter
        # overall:year
        # overall:custom:2025-01-01:2025-03-31
        parts = (cb.data or "overall:month").split(":")
        # parts[0] == "overall"
        kind = parts[1] if len(parts) >= 2 else "month"
        period_key = kind
        if kind == "custom" and len(parts) >= 4:
            period_key = f"{kind}:{parts[2]}:{parts[3]}"
        await _send_overall_for_period(cb, period_key)
    except Exception as e:
        await cb.message.answer(f"⚠️ Ошибка при разборе периода:\n{hcode(str(e))}")
