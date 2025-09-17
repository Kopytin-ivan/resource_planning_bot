# bot/handlers/add_project.py
from __future__ import annotations

import re, asyncio
from datetime import date, timedelta, datetime
from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold, hcode
from aiogram.enums import ChatAction

from ..keyboards.units import units_keyboard
from ..gas_client import list_units_min, list_units_and_managers, add_project

router = Router(name="add_project")

class AddProj(StatesGroup):
    choose_unit = State()
    enter_name  = State()
    choose_mgr  = State()
    enter_dates = State()
    confirm     = State()

def _iso(d: date) -> str: return d.strftime("%Y-%m-%d")
def _to_iso_or_none(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t: return None
    m = re.fullmatch(r"\+(\d{1,3})", t)
    if m:
        d = date.today() + timedelta(days=int(m.group(1)))
        return _iso(d)
    m = re.fullmatch(r"(\d{1,2})[.\-\/](\d{1,2})(?:[.\-\/](\d{2,4}))?", t)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2)); yy = m.group(3)
        yyyy = date.today().year if yy is None else (2000+int(yy) if len(yy)==2 else int(yy))
        try: return _iso(date(yyyy, mm, dd))
        except ValueError: return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try: datetime.strptime(t, "%Y-%m-%d"); return t
        except ValueError: return None
    return None

def _kb_yes_no() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="addproj:confirm"),
        InlineKeyboardButton(text="↩️ Исправить",  callback_data="addproj:fix"),
    ]])

def _kb_mgr_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Выбрать из списка", callback_data="addproj:mgr_pick"),
        InlineKeyboardButton(text="Ввести вручную",   callback_data="addproj:mgr_manual"),
        InlineKeyboardButton(text="Пропустить",        callback_data="addproj:mgr_skip"),
    ]])

def _kb_date_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без дат", callback_data="addproj:date_none")],
        [InlineKeyboardButton(text="Только дедлайн", callback_data="addproj:date_deadline")],
        [InlineKeyboardButton(text="Период (старт—конец)", callback_data="addproj:date_range")],
    ])

async def _keep_typing(msg: Message | CallbackQuery, stop: asyncio.Event):
    bot = (msg.message.bot if isinstance(msg, CallbackQuery) else msg.bot)
    chat_id = (msg.message.chat.id if isinstance(msg, CallbackQuery) else msg.chat.id)
    while not stop.is_set():
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        try: await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError: pass

@router.message(F.text == "➕ Добавить проект")
async def start_add(msg: Message, state: FSMContext):
    data = await list_units_min()
    units = data.get("units") or []
    tops = [u for u in units if "." not in str(u.get("code", ""))]
    await state.set_state(AddProj.choose_unit)
    kb = units_keyboard(tops, page=1, action_prefix="addproj_top")
    await msg.answer(hbold("Выбери отдел для нового проекта:"), reply_markup=kb)

@router.callback_query(F.data.startswith("addproj_top:pick:"))
async def on_top_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    data = await list_units_min()
    units = data.get("units") or []
    subs = [u for u in units if str(u.get("top")) == str(code) and "." in str(u.get("code",""))]
    if subs:
        kb = units_keyboard(subs, page=1, action_prefix=f"addproj_sub:{code}")
        await cb.message.edit_text(hbold(f"Отдел {code}. Выбери подюнит:"), reply_markup=kb)
    else:
        await state.update_data(unit=code)
        await state.set_state(AddProj.enter_name)
        await cb.message.answer(hbold(f"Отдел выбран: {code}.\nВведи *название проекта*:"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("addproj_sub:"))
async def on_sub_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    parts = (cb.data or "").split(":")
    if len(parts) >= 4 and parts[-2] == "pick":
        code = parts[-1]
        await state.update_data(unit=code)
        await state.set_state(AddProj.enter_name)
        await cb.message.answer(hbold(f"Подюнит выбран: {code}.\nВведи *название проекта*:"), parse_mode="Markdown")

@router.message(AddProj.enter_name)
async def on_name(msg: Message, state: FSMContext):
    name = (msg.text or "").strip()
    if not name:
        await msg.answer("Название не должно быть пустым. Введи ещё раз.")
        return
    await state.update_data(project=name)
    await state.set_state(AddProj.choose_mgr)
    await msg.answer(hbold("Менеджер (необязательно):"), reply_markup=_kb_mgr_actions())

@router.callback_query(F.data == "addproj:mgr_skip")
async def mgr_skip(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(manager=None)
    await state.set_state(AddProj.enter_dates)
    await cb.message.answer(hbold("Даты (необязательно):"), reply_markup=_kb_date_actions())

@router.callback_query(F.data == "addproj:mgr_manual")
async def mgr_manual(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer("Введи менеджера (например, «Савина Е.»).")
    await state.set_state(AddProj.choose_mgr)

@router.callback_query(F.data == "addproj:mgr_pick")
async def mgr_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await list_units_and_managers()
    all_mgrs: list[str] = data.get("managers") or []
    buttons = [[InlineKeyboardButton(text=m, callback_data=f"addproj:mgr_choose:{i}")]
               for i, m in enumerate(all_mgrs[:12])]
    buttons.append([InlineKeyboardButton(text="Другое (ввести)", callback_data="addproj:mgr_manual")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await cb.message.answer("Выбери менеджера:", reply_markup=kb)
    await state.update_data(_mgr_pool=all_mgrs)

@router.callback_query(F.data.startswith("addproj:mgr_choose:"))
async def mgr_choose(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    idx = int((cb.data or "").split(":")[-1])
    pool: list[str] = (await state.get_data()).get("_mgr_pool") or []
    manager = pool[idx] if 0 <= idx < len(pool) else None
    await state.update_data(manager=manager, _mgr_pool=None)
    await state.set_state(AddProj.enter_dates)
    await cb.message.answer(hbold(f"Менеджер: {manager or '—'}"))
    await cb.message.answer(hbold("Даты (необязательно):"), reply_markup=_kb_date_actions())

@router.message(AddProj.choose_mgr)
async def mgr_manual_text(msg: Message, state: FSMContext):
    manager = (msg.text or "").strip()
    if not manager:
        await msg.answer("Пусто. Введи менеджера или нажми «Пропустить».")
        return
    await state.update_data(manager=manager)
    await state.set_state(AddProj.enter_dates)
    await msg.answer(hbold("Даты (необязательно):"), reply_markup=_kb_date_actions())

@router.callback_query(F.data == "addproj:date_none")
async def date_none(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(start=None, end=None)
    await _show_confirm(cb, state)

@router.callback_query(F.data == "addproj:date_deadline")
async def date_deadline(cb: CallbackQuery, state: FSMContext):
    await cb.answer("Введи дату окончания (30.09 / 2025-09-30 / +14).", show_alert=False)
    await state.set_state(AddProj.enter_dates)

@router.callback_query(F.data == "addproj:date_range")
async def date_range(cb: CallbackQuery, state: FSMContext):
    await cb.answer("Введи период: 12.09.25 - 30.11.25 (или ISO).", show_alert=False)
    await state.set_state(AddProj.enter_dates)

@router.message(AddProj.enter_dates)
async def dates_input(msg: Message, state: FSMContext):
    t = (msg.text or "").strip()
    m = re.match(r"(.+?)\s*[-–]\s*(.+)$", t)
    if m:
        s_iso, e_iso = _to_iso_or_none(m.group(1)), _to_iso_or_none(m.group(2))
        if not e_iso:
            await msg.answer("Не распознал дату окончания. Пример: 12.09.2025 - 30.11.2025")
            return
        await state.update_data(start=s_iso, end=e_iso); await _show_confirm(msg, state); return
    e_iso = _to_iso_or_none(t)
    if e_iso:
        await state.update_data(start=None, end=e_iso); await _show_confirm(msg, state); return
    await msg.answer("Не удалось распознать. Примеры: «30.09», «2025-10-15», «+14», «12.09-30.11.25».")

async def _show_confirm(msg_or_cb: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    unit, name = data.get("unit"), data.get("project")
    manager, start, end = data.get("manager") or "—", data.get("start") or "—", data.get("end") or "—"
    text = f"{hbold('Проверь данные:')}\nUNIT: {hcode(unit)}\nПроект: {name}\nМенеджер: {manager}\nСтарт: {start}\nКонец: {end}"
    if isinstance(msg_or_cb, CallbackQuery): await msg_or_cb.message.answer(text, reply_markup=_kb_yes_no())
    else:                                    await msg_or_cb.answer(text, reply_markup=_kb_yes_no())
    await state.set_state(AddProj.confirm)

@router.callback_query(F.data == "addproj:fix")
async def on_fix(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AddProj.enter_name)
    await cb.message.answer("Ок, введи *название проекта* ещё раз:", parse_mode="Markdown")

@router.callback_query(F.data == "addproj:confirm")
async def on_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    unit, name = data.get("unit"), data.get("project")
    manager, start, end = data.get("manager"), data.get("start"), data.get("end")
    if not unit or not name:
        await cb.message.answer("Не хватает данных. Начни заново: «➕ Добавить проект»."); await state.clear(); return
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(cb, stop))
    loading = await cb.message.answer("⏳ Добавляю проект…")
    try:
        resp = await add_project(unit=unit, project=name, start=start, end=end, manager=manager)
        if not resp or not resp.get("ok"): raise RuntimeError(resp.get("error") or "unknown error")
        unit_label = resp.get("unit") or unit; row = resp.get("row"); note = resp.get("note") or "ok"
        await loading.edit_text(
            f"✅ Проект добавлен\n{hbold(unit_label)}\n• {name}\n"
            f"{'(менеджер: ' + manager + ')' if manager else ''}\n"
            f"{'(строка: ' + str(row) + ')' if row else ''}\n({note})"
        )
        await state.clear()
    except Exception as e:
        await loading.edit_text(f"⚠️ Ошибка при добавлении: {hcode(str(e))}")
    finally:
        stop.set(); typing_task.cancel()
