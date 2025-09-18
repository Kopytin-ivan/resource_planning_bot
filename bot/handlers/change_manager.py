# bot/handlers/change_manager.py
from __future__ import annotations

import asyncio
from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatAction
from aiogram.utils.markdown import hbold, hcode

from ..keyboards.units import units_keyboard
from ..keyboards.projects import projects_keyboard
from ..keyboards.main_menu import main_menu_kb
from ..gas_client import (
    list_units_min,
    list_projects_for_unit,
    list_managers, 
    list_units_and_managers,
    set_manager as gas_set_manager,
)

router = Router(name="change_manager")

# ---- FSM ----
class ChangeMgr(StatesGroup):
    choose_unit_top = State()
    choose_unit_sub = State()
    choose_project  = State()
    choose_manager  = State()

# ---- helpers ----
def _managers_kb(managers: list[str], page: int, action_prefix: str) -> InlineKeyboardMarkup:
    PAGE = 10
    if page < 1:
        page = 1
    start = (page - 1) * PAGE
    end = start + PAGE

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=m, callback_data=f"{action_prefix}:pick:{m}")]
        for m in managers[start:end]
    ]

    nav: list[InlineKeyboardButton] = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"{action_prefix}:page:{page-1}"))
    if end < len(managers):
        nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"{action_prefix}:page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _send_top_units(msg: Message | CallbackQuery):
    data = await list_units_min()
    units = data.get("units") or []
    tops = [u for u in units if "." not in str(u.get("code") or "")]
    kb = units_keyboard(tops, page=1, action_prefix="cm_top")
    text = hbold("Выбери отдел для изменения менеджера:")
    if isinstance(msg, Message):
        await msg.answer(text, reply_markup=kb)
    else:
        await msg.message.edit_text(text, reply_markup=kb)

async def _send_sub_units(cb: CallbackQuery, top_code: str, page: int = 1):
    data = await list_units_min()
    units = data.get("units") or []
    subs = [u for u in units if str(u.get("top")) == str(top_code) and "." in str(u.get("code") or "")]
    if not subs:
        await _send_projects(cb, code=top_code)
        return
    kb = units_keyboard(subs, page=page, action_prefix=f"cm_sub:{top_code}")
    await cb.message.edit_text(hbold(f"Отдел {top_code}. Выбери подюнит:"), reply_markup=kb)

async def _send_projects(cb: CallbackQuery, code: str, page: int = 1):
    resp = await list_projects_for_unit(code)
    projects = resp.get("projects") or []
    if not projects:
        await cb.message.edit_text(f"{hbold(resp.get('unit') or code)}\nПроекты не найдены.")
        return
    kb = projects_keyboard(projects, page=page, action_prefix=f"cm_proj:{code}")
    await cb.message.edit_text(hbold(f"{resp.get('unit') or code}\nВыбери проект:"), reply_markup=kb)

async def _send_managers(cb: CallbackQuery, unit: str, project: str, page: int = 1):
    resp = await list_managers()  # ← лёгкий вызов
    managers = sorted(set(resp.get("managers") or []))
    if not managers:
        await cb.message.edit_text("⚠️ В таблице не настроена валидация списка менеджеров в колонке B.")
        return
    kb = _managers_kb(managers, page=page, action_prefix=f"cm_mgr:{unit}:{project}")
    await cb.message.edit_text(hbold(f"{unit}\nПроект: {project}\nВыбери менеджера:"), reply_markup=kb)


# ---- Entry point ----
@router.message(F.text == "👤 Изменить менеджера")
async def start_change_manager(msg: Message, state: FSMContext):
    await state.set_state(ChangeMgr.choose_unit_top)
    await _send_top_units(msg)

# ---- Top unit paging/pick ----
@router.callback_query(F.data.startswith("cm_top:page:"))
async def cm_top_page(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    try:
        page = int((cb.data or "cm_top:page:1").split(":")[-1])
    except Exception:
        page = 1
    data = await list_units_min()
    units = data.get("units") or []
    tops = [u for u in units if "." not in str(u.get("code") or "")]
    kb = units_keyboard(tops, page=page, action_prefix="cm_top")
    await cb.message.edit_text(hbold("Выбери отдел для изменения менеджера:"), reply_markup=kb)

@router.callback_query(F.data.startswith("cm_top:pick:"))
async def cm_top_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    await state.update_data(unit_top=code)
    await state.set_state(ChangeMgr.choose_unit_sub)
    await _send_sub_units(cb, top_code=code, page=1)

# ---- Subunit paging/pick ----
@router.callback_query(F.data.startswith("cm_sub:"))
async def cm_sub_router(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    parts = (cb.data or "cm_sub::").split(":")
    # cm_sub:<top>:page:<n>
    # cm_sub:<top>:pick:<code>
    if len(parts) < 3:
        return
    top_code = parts[1]
    action = parts[2]
    if action == "page":
        try:
            page = int(parts[3])
        except Exception:
            page = 1
        await _send_sub_units(cb, top_code=top_code, page=page)
        return
    if action == "pick":
        code = parts[3]
        await state.update_data(unit=code)
        await state.set_state(ChangeMgr.choose_project)
        await _send_projects(cb, code=code, page=1)

# ---- Projects paging/pick (исправлено) ----
@router.callback_query(F.data.startswith("cm_proj:"))
async def cm_proj_router(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    # Формат: "cm_proj:<unit>:page:<n>" или "cm_proj:<unit>:pick:<token>"
    try:
        _, unit, tail = (cb.data or "cm_proj::").split(":", 2)
    except ValueError:
        return

    if tail.startswith("page:"):
        try:
            page = int(tail.split(":", 1)[1])
        except Exception:
            page = 1
        await _send_projects(cb, code=unit, page=page)
        return

    if tail.startswith("pick:"):
        token = tail.split("pick:", 1)[1]  # может быть целым индексом или именем
        project = token
        # если пришёл индекс — подменяем на имя
        if token.isdigit():
            idx = int(token)
            resp = await list_projects_for_unit(unit)
            plist = resp.get("projects") or []
            if 0 <= idx < len(plist):
                project = plist[idx]
        await state.update_data(unit=unit, project=project)
        await state.set_state(ChangeMgr.choose_manager)
        await _send_managers(cb, unit=unit, project=project, page=1)

# ---- Managers paging/pick (исправлено) ----
@router.callback_query(F.data.startswith("cm_mgr:"))
async def cm_mgr_router(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    unit = data.get("unit")
    project = data.get("project")

    payload = cb.data or ""
    if ":page:" in payload:
        try:
            page = int(payload.rsplit(":", 1)[-1])
        except Exception:
            page = 1
        await _send_managers(cb, unit=unit, project=project, page=page)
        return

    if ":pick:" in payload:
        manager = payload.split(":pick:", 1)[1]
        await _apply_manager(cb, unit=unit, project=project, manager=manager, state=state)

async def _apply_manager(cb: CallbackQuery, unit: str, project: str, manager: str, state: FSMContext):
    # сервисное «печатает…»
    stop = asyncio.Event()
    async def typer():
        try:
            while not stop.is_set():
                await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
                await asyncio.sleep(3)
        except Exception:
            pass
    typing_task = asyncio.create_task(typer())

    try:
        wait = await cb.message.edit_text("⏳ Ставлю менеджера…")
        resp = await gas_set_manager(unit=unit, project=project, manager=manager)
        if not resp or not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "unknown error")
        unit_label = resp.get("unit") or unit
        proj = resp.get("project") or project
        mgr = resp.get("manager") or manager
        await wait.edit_text(f"✅ Готово\n{hbold(unit_label)}\n• {proj}\nменеджер: {hbold(mgr)}")
        await state.clear()
    except Exception as e:
        try:
            await cb.message.edit_text(f"⚠️ Ошибка при смене менеджера:\n{hcode(str(e))}")
        except Exception:
            await cb.message.answer(f"⚠️ Ошибка при смене менеджера:\n{hcode(str(e))}")
    finally:
        stop.set(); typing_task.cancel()

# generic "home" (inline back to main menu)
@router.callback_query(F.data == "home")
async def on_home(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("Главное меню:", reply_markup=main_menu_kb())
