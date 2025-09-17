# bot/keyboards/periods.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class PeriodCB(CallbackData, prefix="prd"):  # короткий префикс
    scope: str    # "load_all" | "load_unit__<unit>" | "endings__<unit>"
    period: str   # "this_month" | "next_month" | "quarter" | "half_year" | "year" | "none"

def _safe_scope(scope: str) -> str:
    # aiogram использует ":" как разделитель → в значениях его быть НЕ должно
    return (scope or "").replace(":", "__")

def periods_kb(scope: str) -> InlineKeyboardMarkup:
    scope = _safe_scope(scope)
    rows = [
        [
            InlineKeyboardButton(text="Этот месяц",  callback_data=PeriodCB(scope=scope, period="this_month").pack()),
            InlineKeyboardButton(text="След. месяц", callback_data=PeriodCB(scope=scope, period="next_month").pack()),
        ],
        [
            InlineKeyboardButton(text="Квартал",     callback_data=PeriodCB(scope=scope, period="quarter").pack()),
            InlineKeyboardButton(text="Полгода",     callback_data=PeriodCB(scope=scope, period="half_year").pack()),
        ],
        [
            InlineKeyboardButton(text="Год",         callback_data=PeriodCB(scope=scope, period="year").pack()),
            InlineKeyboardButton(text="Без периода", callback_data=PeriodCB(scope=scope, period="none").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
