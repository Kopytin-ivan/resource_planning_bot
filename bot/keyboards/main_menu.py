from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Общая загруженность", callback_data="all_load")],
        [InlineKeyboardButton(text="🧩 Загрузка юнита",      callback_data="unit_load")],
        [InlineKeyboardButton(text="ℹ️ Помощь",              callback_data="help")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
