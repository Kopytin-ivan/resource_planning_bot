# bot/keyboards/main_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📊 Общая загруженность"), KeyboardButton(text="🧩 Загруженность юнита")],
        [KeyboardButton(text="🔚 Завершения"), KeyboardButton(text="➕ Добавить проект")],
        [KeyboardButton(text="⚙️ Ещё")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,   # компактнее
        is_persistent=True,     # остается всегда
        one_time_keyboard=False # не скрывать после нажатия
    )
