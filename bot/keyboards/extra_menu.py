# bot/keyboards/extra_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def extra_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="✏️ Изменить сроки проекта")],
        [KeyboardButton(text="👤 Изменить менеджера"), KeyboardButton(text="🗑 Удалить проект")],
        [KeyboardButton(text="🟡 На согласовании/закрытие"), KeyboardButton(text="⏸ На паузе/не начат")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )
