# bot/keyboards/units.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PAGE_SIZE = 10

def units_keyboard(units: list[dict], page: int, action_prefix: str = "unitload") -> InlineKeyboardMarkup:
    """
    Рисует список юнитов с пагинацией.
    units: список словарей от GAS: { code: "2.1", label: "(UNIT 2.1) ..." }
    page: 1..N
    action_prefix: префикс callback, напр. "unitload"
    """
    # границы страницы
    if page < 1:
        page = 1
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    # строки юнитов
    rows: list[list[InlineKeyboardButton]] = []
    for u in units[start:end]:
        title = u.get("label") or f"(UNIT {u.get('code')})"
        code = u.get("code")
        rows.append([InlineKeyboardButton(title, callback_data=f"{action_prefix}:pick:{code}")])

    # навигация
    nav: list[InlineKeyboardButton] = []
    if start > 0:
        nav.append(InlineKeyboardButton("‹ Назад", callback_data=f"{action_prefix}:page:{page-1}"))
    if end < len(units):
        nav.append(InlineKeyboardButton("Далее ›", callback_data=f"{action_prefix}:page:{page+1}"))
    if nav:
        rows.append(nav)

    # кнопка "домой"
    rows.append([InlineKeyboardButton("🏠 В меню", callback_data="home")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

__all__ = ["units_keyboard"]
