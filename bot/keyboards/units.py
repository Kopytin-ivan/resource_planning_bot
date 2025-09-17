from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PAGE_SIZE = 10

def units_keyboard(
    units: list[dict],
    page: int,
    action_prefix: str,
    extra_rows: list[list[InlineKeyboardButton]] | None = None
) -> InlineKeyboardMarkup:
    """
    Пагинируемый список юнитов.
    - units: {"code": "2.1", "top": "2", "label": "Александр Аляев"} — label берём из GAS
    - action_prefix:
        "unitload_top"           → "unitload_top:pick:<code>" / "unitload_top:page:<n>"
        "unitload_sub:<topCode>" → "unitload_sub:<topCode>:pick:<code>" / ...:page:<n>
    """
    if page < 1:
        page = 1
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    rows: list[list[InlineKeyboardButton]] = []
    for u in units[start:end]:
        title = u.get("label") or f"(UNIT {u.get('code')})"
        code = u.get("code")
        rows.append([InlineKeyboardButton(text=title, callback_data=f"{action_prefix}:pick:{code}")])

    nav: list[InlineKeyboardButton] = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"{action_prefix}:page:{page-1}"))
    if end < len(units):
        nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"{action_prefix}:page:{page+1}"))
    if nav:
        rows.append(nav)

    if extra_rows:
        rows.extend(extra_rows)

    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
