from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def periods_keyboard(next_action: str) -> InlineKeyboardMarkup:
    # next_action — префикс, который мы будем ловить в хендлерах
    rows = [
        [
            InlineKeyboardButton("Этот месяц",  callback_data=f"{next_action}:preset:this_month"),
            InlineKeyboardButton("След. месяц", callback_data=f"{next_action}:preset:next_month")
        ],
        [
            InlineKeyboardButton("Квартал",     callback_data=f"{next_action}:preset:quarter"),
            InlineKeyboardButton("Год",         callback_data=f"{next_action}:preset:year")
        ],
        [InlineKeyboardButton("Без периода",   callback_data=f"{next_action}:preset:none")],
        [InlineKeyboardButton("🏠 В меню",     callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
