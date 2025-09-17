from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Общая загруженность", callback_data="all_load")],
        [InlineKeyboardButton(text="🧩 Загрузка юнита", callback_data="unit_load")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
