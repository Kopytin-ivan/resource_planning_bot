# bot/keyboards/projects.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PAGE_SIZE = 10

def projects_keyboard(
    projects: list[str],
    page: int,
    action_prefix: str,  # напр. "edproj"
    extra_rows: list[list[InlineKeyboardButton]] | None = None
) -> InlineKeyboardMarkup:
    if page < 1:
        page = 1
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    rows: list[list[InlineKeyboardButton]] = []
    for i, name in enumerate(projects[start:end], start=start):
        title = name if len(name) <= 64 else (name[:61] + "…")
        rows.append([InlineKeyboardButton(text=title, callback_data=f"{action_prefix}:pick:{i}")])

    nav: list[InlineKeyboardButton] = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"{action_prefix}:page:{page-1}"))
    if end < len(projects):
        nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"{action_prefix}:page:{page+1}"))
    if nav:
        rows.append(nav)

    if extra_rows:
        rows.extend(extra_rows)

    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
