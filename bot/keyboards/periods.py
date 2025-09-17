# bot/keyboards/periods.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class PeriodCB(CallbackData, prefix="prd"):  # безопасный короткий префикс
    scope: str    # "load_all" или "load_unit:<unit>"
    period: str   # "this_month" | "next_month" | "quarter" | "half_year" | "year" | "none"

def periods_kb(scope: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Этот месяц", callback_data=PeriodCB(scope=scope, period="this_month").pack()),
            InlineKeyboardButton(text="След. месяц", callback_data=PeriodCB(scope=scope, period="next_month").pack()),
        ],
        [
            InlineKeyboardButton(text="Квартал", callback_data=PeriodCB(scope=scope, period="quarter").pack()),
            InlineKeyboardButton(text="Полгода", callback_data=PeriodCB(scope=scope, period="half_year").pack()),
        ],
        [
            InlineKeyboardButton(text="Год", callback_data=PeriodCB(scope=scope, period="year").pack()),
            InlineKeyboardButton(text="Без периода", callback_data=PeriodCB(scope=scope, period="none").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
