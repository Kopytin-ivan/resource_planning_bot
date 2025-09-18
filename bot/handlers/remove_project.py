# bot/handlers/remove_project.py
from __future__ import annotations

import re
from typing import List, Dict, Any, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.markdown import hbold

from ..gas_client import list_units_min, list_projects_for_unit, remove_project

router = Router(name="remove_project")

# ---------- FSM ----------
class DelStates(StatesGroup):
    choose_top = State()
    choose_unit = State()
    choose_project = State()
    confirm = State()


# ---------- helpers ----------
_RX_UNIT_PREFIX = re.compile(r"^\(\s*UNIT\s*[0-9]+(?:\.[0-9]+)?\)\s*", re.I)

def _strip_unit_prefix(label: str) -> str:
    return _RX_UNIT_PREFIX.sub("", str(label or "")).strip()

def _mk_kb(rows: List[List[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=txt, callback_data=cb) for txt, cb in row]
            for row in rows
        ]
    )

def _chunk(lst: List[Any], n: int) -> List[List[Any]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

# bot/handlers/remove_project.py

def _page_kb(items: List[tuple[str, str]], page: int, per_page: int,
             back_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    total = len(items)
    start = page * per_page
    end = min(total, start + per_page)
    slice_ = items[start:end]

    rows: List[List[tuple[str, str]]] = []

    # кладём по 2 кнопки в ряд, но без распаковки
    i = 0
    while i < len(slice_):
        first = slice_[i]
        second = slice_[i + 1] if i + 1 < len(slice_) else None
        if second:
            rows.append([first, second])
            i += 2
        else:
            rows.append([first])
            i += 1

    # навигация
    nav: List[tuple[str, str]] = []
    if page > 0:
        nav.append(("« Назад", f"del:page:{page-1}"))
    if end < total:
        nav.append(("Вперёд »", f"del:page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([("⬅️ Назад", back_cb), ("❌ Отмена", cancel_cb)])
    return _mk_kb(rows)

# ---------- STEP 0: entry ----------
@router.message(F.text == "🗑 Удалить проект")
async def start_delete(msg: Message, state: FSMContext):
    wait = await msg.answer("⏳ Загрузка…")
    try:
        resp = await list_units_min()
        if not resp or not resp.get("ok"):
            raise RuntimeError((resp or {}).get("error") or "list_units_min failed")

        units: List[Dict[str, Any]] = resp.get("units") or []
        # сгруппируем по верхнему юниту
        by_top: Dict[str, Dict[str, Any]] = {}
        for u in units:
            code = str(u.get("code") or "")
            top = str(u.get("top") or "")
            label = str(u.get("label") or "")
            by_top.setdefault(top, {"top": top, "display": _strip_unit_prefix(label)})
            # если это точный заголовок (без подюнита), используем его в качестве "display"
            if "." not in code:
                by_top[top]["display"] = _strip_unit_prefix(label)

        tops_sorted = sorted(by_top.values(), key=lambda x: (int(x["top"]) if x["top"].isdigit() else 999, x["top"]))

        # построим кнопки топ-юнитов
        items = [(f"UNIT {t['top']} — {t['display'] or ''}".strip(), f"del:top:{t['top']}") for t in tops_sorted]
        kb = _page_kb(items, page=0, per_page=10, back_cb="del:cancel", cancel_cb="del:cancel")
        await state.update_data(_tops=items, _page=0)
        await state.set_state(DelStates.choose_top)
        await wait.edit_text(hbold("Выбери верхний UNIT"), reply_markup=kb)
    except Exception as e:
        await wait.edit_text(f"⚠️ Не удалось загрузить юниты.\n<code>{e}</code>")

# пагинация топ-юнитов
@router.callback_query(DelStates.choose_top, F.data.startswith("del:page:"))
async def page_tops(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("_tops") or []
    try:
        page = int(cb.data.split(":")[-1])
    except Exception:
        page = 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:cancel", cancel_cb="del:cancel")
    await state.update_data(_page=page)
    await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()

# выбор топ-юнита
@router.callback_query(DelStates.choose_top, F.data.startswith("del:top:"))
async def pick_top(cb: CallbackQuery, state: FSMContext):
    top = cb.data.split(":")[-1]
    wait = await cb.message.edit_text("⏳ Загрузка…")
    try:
        resp = await list_units_min()
        if not resp or not resp.get("ok"):
            raise RuntimeError((resp or {}).get("error") or "list_units_min failed")

        units: List[Dict[str, Any]] = resp.get("units") or []
        subs = [u for u in units if str(u.get("top")) == top and "." in str(u.get("code") or "")]
        subs_sorted = sorted(subs, key=lambda u: tuple(int(x) if x.isdigit() else 0 for x in str(u["code"]).split(".")))

        # кнопки подюнитов + "верхний UNIT без подюнита"
        items = []
        items.append((f"⬆️ UNIT {top} (без подюнита)", f"del:unit:{top}"))
        for u in subs_sorted:
            code = str(u.get("code"))
            items.append((f"UNIT {code} — {_strip_unit_prefix(u.get('label'))}", f"del:unit:{code}"))

        kb = _page_kb(items, page=0, per_page=10, back_cb="del:back:tops", cancel_cb="del:cancel")
        await state.update_data(top=top, _units=items, _page=0)
        await state.set_state(DelStates.choose_unit)
        await wait.edit_text(hbold(f"UNIT {top} — выбери подюнит"), reply_markup=kb)
    except Exception as e:
        await wait.edit_text(f"⚠️ Не удалось загрузить подюниты.\n<code>{e}</code>")

# назад к топам
@router.callback_query(DelStates.choose_unit, F.data == "del:back:tops")
async def back_to_tops(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("_tops") or []
    page = data.get("_page") or 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:cancel", cancel_cb="del:cancel")
    await state.set_state(DelStates.choose_top)
    await cb.message.edit_text(hbold("Выбери верхний UNIT"), reply_markup=kb)
    await cb.answer()

# пагинация подюнитов
@router.callback_query(DelStates.choose_unit, F.data.startswith("del:page:"))
async def page_units(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("_units") or []
    try:
        page = int(cb.data.split(":")[-1])
    except Exception:
        page = 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:back:tops", cancel_cb="del:cancel")
    await state.update_data(_page=page)
    await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()

# выбор конкретного (под)юнита -> список проектов
@router.callback_query(DelStates.choose_unit, F.data.startswith("del:unit:"))
async def pick_unit(cb: CallbackQuery, state: FSMContext):
    unit_code = cb.data.split(":")[-1]
    wait = await cb.message.edit_text("⏳ Загрузка…")
    try:
        resp = await list_projects_for_unit(unit=unit_code)
        if not resp or not resp.get("ok"):
            raise RuntimeError((resp or {}).get("error") or "list_projects_for_unit failed")

        unit_label = resp.get("unit") or f"(UNIT {unit_code})"
        projects: List[str] = resp.get("projects") or []

        if not projects:
            await wait.edit_text(f"{hbold(unit_label)}\nПроекты не найдены.")
            return

        # строим список кнопок-проектов
        items = [(name, f"del:proj:{i}") for i, name in enumerate(projects)]
        kb = _page_kb(items, page=0, per_page=10, back_cb="del:back:units", cancel_cb="del:cancel")

        await state.update_data(unit=unit_code, unit_label=unit_label, projects=projects, _items=items, _page=0)
        await state.set_state(DelStates.choose_project)
        await wait.edit_text(hbold(f"{unit_label}\nВыбери проект для удаления:"), reply_markup=kb)
    except Exception as e:
        await wait.edit_text(f"⚠️ Не удалось загрузить проекты.\n<code>{e}</code>")

# назад к выбору подюнита
@router.callback_query(DelStates.choose_project, F.data == "del:back:units")
async def back_to_units(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    top = data.get("top")
    items = data.get("_units") or []
    page = data.get("_page") or 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:back:tops", cancel_cb="del:cancel")
    await state.set_state(DelStates.choose_unit)
    await cb.message.edit_text(hbold(f"UNIT {top} — выбери подюнит"), reply_markup=kb)
    await cb.answer()

# пагинация проектов
@router.callback_query(DelStates.choose_project, F.data.startswith("del:page:"))
async def page_projects(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("_items") or []
    try:
        page = int(cb.data.split(":")[-1])
    except Exception:
        page = 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:back:units", cancel_cb="del:cancel")
    await state.update_data(_page=page)
    await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()

# выбор проекта -> подтверждение
@router.callback_query(DelStates.choose_project, F.data.startswith("del:proj:"))
async def pick_project(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    projects: List[str] = data.get("projects") or []
    try:
        idx = int(cb.data.split(":")[-1])
    except Exception:
        await cb.answer("Ошибка выбора", show_alert=True)
        return
    if idx < 0 or idx >= len(projects):
        await cb.answer("Проект не найден", show_alert=True)
        return
    project = projects[idx]

    kb = _mk_kb([
        [("✅ Да, удалить", "del:confirm:yes"), ("↩️ Нет, назад", "del:back:proj")],
        [("❌ Отмена", "del:cancel")]
    ])
    await state.update_data(project=project)
    await state.set_state(DelStates.confirm)
    await cb.message.edit_text(hbold(f"Удалить проект?\n\n{project}"), reply_markup=kb)
    await cb.answer()

# назад к списку проектов из подтверждения
@router.callback_query(DelStates.confirm, F.data == "del:back:proj")
async def back_from_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    unit_label = data.get("unit_label") or ""
    items = data.get("_items") or []
    page = data.get("_page") or 0
    kb = _page_kb(items, page=page, per_page=10, back_cb="del:back:units", cancel_cb="del:cancel")
    await state.set_state(DelStates.choose_project)
    await cb.message.edit_text(hbold(f"{unit_label}\nВыбери проект для удаления:"), reply_markup=kb)
    await cb.answer()

# подтверждение удаления
@router.callback_query(DelStates.confirm, F.data == "del:confirm:yes")
async def do_delete(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    unit = data.get("unit")
    unit_label = data.get("unit_label") or f"(UNIT {unit})"
    project = data.get("project")

    wait = await cb.message.edit_text("⏳ Удаляю…")
    try:
        resp = await remove_project(unit=unit, project=project)
        if not resp or not resp.get("ok"):
            raise RuntimeError((resp or {}).get("error") or "remove_project failed")
        await wait.edit_text(f"🗑 Готово.\n{hbold(unit_label)}\nУдалено: {project}")
    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка при удалении.\n<code>{e}</code>")
    finally:
        await state.clear()
    await cb.answer()

# отмена из любого шага
@router.callback_query(F.data == "del:cancel")
async def cancel_any(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Ок, отменил удаление.")
    await cb.answer()
