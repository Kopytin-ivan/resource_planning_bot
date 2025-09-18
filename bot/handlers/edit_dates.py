# bot/handlers/edit_dates.py
from __future__ import annotations
import re, asyncio
from datetime import date, timedelta, datetime
from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold, hcode
from aiogram.enums import ChatAction
from ..keyboards.projects import projects_keyboard
from ..gas_client import list_units_min, extend_deadline, move_project, list_projects_for_unit
from ..gas_client import list_units_min, extend_deadline, move_project, list_projects_for_unit, get_project_info

from ..keyboards.units import units_keyboard
from ..gas_client import list_units_min, extend_deadline, move_project

router = Router(name="edit_dates")

# ---- FSM ----
class EditDates(StatesGroup):
    choose_unit  = State()
    choose_project = State()
    enter_name   = State()
    choose_mode  = State()
    enter_dates  = State()
    confirm      = State()

# ---- helpers ----
def _iso(d: date) -> str: return d.strftime("%Y-%m-%d")

def _to_iso_or_rel(text: str, base_iso: str | None = None) -> str | None:
    """
    Поддержка:
      - +N: от BASE (если известен), иначе от сегодня
      - dd.mm[.yy], dd-mm[-yy], ISO YYYY-MM-DD
    """
    t = (text or "").strip().lower()
    if not t:
        return None

    # +N дней
    m = re.fullmatch(r"\+(\d{1,3})", t)
    if m:
        n = int(m.group(1))
        # базовая дата — текущий дедлайн (если есть), иначе сегодня
        if base_iso:
            y, mth, dd = map(int, base_iso.split("-"))
            base = date(y, mth, dd)
        else:
            base = date.today()
        return (base + timedelta(days=n)).strftime("%Y-%m-%d")

    # DD.MM[.YY(YY)]
    m = re.fullmatch(r"(\d{1,2})[.\-\/](\d{1,2})(?:[.\-\/](\d{2,4}))?", t)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2))
        yy     = m.group(3)
        if yy is None:
            yyyy = date.today().year
        else:
            yyyy = int(yy)
            if yyyy < 100:
                yyyy = 2000 + yyyy
        try:
            return date(yyyy, mm, dd).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try:
            datetime.strptime(t, "%Y-%m-%d")
            return t
        except ValueError:
            return None

    return None


def _to_iso_or_none(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t: return None
    # +N
    m = re.fullmatch(r"\+(\d{1,3})", t)
    if m: return _iso(date.today() + timedelta(days=int(m.group(1))))
    # dd.mm[.yy]
    m = re.fullmatch(r"(\d{1,2})[.\-\/](\d{1,2})(?:[.\-\/](\d{2,4}))?", t)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2))
        y = m.group(3)
        yyyy = date.today().year if y is None else (2000 + int(y) if len(y)==2 else int(y))
        try: return _iso(date(yyyy, mm, dd))
        except ValueError: return None
    # ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try: datetime.strptime(t, "%Y-%m-%d"); return t
        except ValueError: return None
    return None

def _kb_mode() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔚 Только дедлайн", callback_data="ed:mode:end")],
        [InlineKeyboardButton(text="📅 Период (старт—конец)", callback_data="ed:mode:range")],
    ])

def _kb_yes_no() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Применить", callback_data="ed:ok"),
        InlineKeyboardButton(text="↩️ Исправить", callback_data="ed:fix"),
    ]])

async def _typing(msg_or_cb, stop: asyncio.Event):
    bot = (msg_or_cb.message.bot if isinstance(msg_or_cb, CallbackQuery) else msg_or_cb.bot)
    chat_id = (msg_or_cb.message.chat.id if isinstance(msg_or_cb, CallbackQuery) else msg_or_cb.chat.id)
    while not stop.is_set():
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        try: await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError: pass

# ---- entry point from extra menu ----
@router.message(F.text == "✏️ Изменить сроки проекта")
async def start_edit(msg: Message, state: FSMContext):
    data = await list_units_min()
    units = data.get("units") or []
    tops = [u for u in units if "." not in str(u.get("code",""))]
    await state.set_state(EditDates.choose_unit)
    kb = units_keyboard(tops, page=1, action_prefix="ed_top")
    await msg.answer(hbold("Выбери отдел:"), reply_markup=kb)

@router.callback_query(F.data.startswith("ed_top:pick:"))
async def on_top_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    data = await list_units_min()
    units = data.get("units") or []
    subs = [u for u in units if str(u.get("top")) == str(code) and "." in str(u.get("code",""))]
    if subs:
        kb = units_keyboard(subs, page=1, action_prefix=f"ed_sub:{code}")
        await cb.message.edit_text(hbold(f"Отдел {code}. Выбери подюнит:"), reply_markup=kb)
    else:
        await _show_projects_list(cb, state, unit_code=code, page=1)

async def _show_projects_list(cb: CallbackQuery, state: FSMContext, unit_code: str, page: int):
    resp = await list_projects_for_unit(unit_code)
    if not resp or not resp.get("ok"):
        err = (resp or {}).get("error") or "неизвестная ошибка"
        await cb.message.answer(f"⚠️ Не удалось получить проекты для UNIT {unit_code}: {err}")
        return
    projects: list[str] = resp.get("projects") or []
    await state.update_data(unit=unit_code, _proj_list=projects, _proj_page=page)
    if not projects:
        await cb.message.answer(f"В (UNIT {unit_code}) проектов не найдено.")
        return
    kb = projects_keyboard(projects, page=page, action_prefix="edproj")
    await state.set_state(EditDates.choose_project)
    await cb.message.edit_text(hbold(f"(UNIT {unit_code})\nВыберите проект:"), reply_markup=kb)

@router.callback_query(F.data.startswith("edproj:page:"))
async def on_proj_page(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    try:
        page = int((cb.data or "").split(":")[-1])
    except Exception:
        page = 1
    d = await state.get_data()
    unit = d.get("unit")
    projects: list[str] = d.get("_proj_list") or []
    if not (unit and projects):
        return
    await state.update_data(_proj_page=page)
    kb = projects_keyboard(projects, page=page, action_prefix="edproj")
    await cb.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("edproj:pick:"))
async def on_proj_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    d = await state.get_data()
    projects: list[str] = d.get("_proj_list") or []
    try:
        idx = int((cb.data or "").split(":")[-1])
    except Exception:
        idx = -1
    if idx < 0 or idx >= len(projects):
        await cb.message.answer("Не удалось определить проект. Попробуйте ещё раз.")
        return

    name = projects[idx]
    unit = d.get("unit")

    # ← тянем текущие даты проекта из GAS
    info = await get_project_info(unit=unit, project=name)
    curr_start = info.get("start")  # 'YYYY-MM-DD' или None
    curr_end   = info.get("end")    # 'YYYY-MM-DD' или None

    await state.update_data(project=name, curr_start=curr_start, curr_end=curr_end)
    await state.set_state(EditDates.choose_mode)

    def _fmt(iso: str | None) -> str:
        if not iso: return "—"
        y, m, d = iso.split("-")
        return f"{d}.{m}.{y}"

    await cb.message.answer(
        hbold(f"Проект: {name}") + f"\nТекущий период: {_fmt(curr_start)} — {_fmt(curr_end)}"
    )
    await cb.message.answer(hbold("Что меняем?"), reply_markup=_kb_mode())



@router.callback_query(F.data.startswith("ed_sub:"))
async def on_sub_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    parts = (cb.data or "").split(":")
    if len(parts) >= 4 and parts[-2] == "pick":
        code = parts[-1]
        await _show_projects_list(cb, state, unit_code=code, page=1)

# ---- pick mode ----
@router.callback_query(F.data.startswith("ed:mode:"))
async def on_mode(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    mode = (cb.data or "").split(":")[-1]  # end | range
    await state.update_data(mode=mode)
    await state.set_state(EditDates.enter_dates)

    d = await state.get_data()
    curr_end = d.get("curr_end")

    def _fmt(iso: str | None) -> str:
        if not iso: return "—"
        y, m, dd = iso.split("-")
        return f"{dd}.{m}.{y}"

    if mode == "end":
        await cb.message.answer(
            f"Введи НОВЫЙ дедлайн (текущий: {_fmt(curr_end)}). "
            "Можно: 30.09, 2025-09-30 или +14"
        )
    else:
        await cb.message.answer(
            "Введи НОВЫЙ период: 12.09.25 - 30.11.25 (или ISO)."
        )

# ---- input dates ----
@router.message(EditDates.enter_dates)
async def on_dates(msg: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode")
    t = (msg.text or "").strip()

    if mode == "end":
        curr_end = data.get("curr_end")
        d_new = _to_iso_or_rel(t, base_iso=curr_end)  # ← ВАЖНО: +N от текущего дедлайна
        if not d_new:
            await msg.answer("Не распознал дату. Примеры: 30.09, 2025-10-15, +14.")
            return
        await state.update_data(new_end=d_new, new_start=None)

    else:
        # период
        m = re.match(r"(.+?)\s*[-–]\s*(.+)$", t)
        if not m:
            await msg.answer("Нужно две даты. Пример: 12.09.25 - 30.11.25")
            return
        s_iso = _to_iso_or_rel(m.group(1))
        e_iso = _to_iso_or_rel(m.group(2))
        if not s_iso or not e_iso:
            await msg.answer("Не распознал даты. Пример: 12.09.25 - 30.11.25")
            return
        await state.update_data(new_start=s_iso, new_end=e_iso)

    # подтверждение
    d2 = await state.get_data()
    unit, proj = d2["unit"], d2["project"]
    start, end = d2.get("new_start") or "—", d2.get("new_end") or "—"
    def _fmt(iso): 
        if not iso or iso == "—": return "—"
        y, mth, dd = iso.split("-"); return f"{dd}.{mth}.{y}"
    txt = f"{hbold('Проверь изменения:')}\nUNIT: {hcode(unit)}\nПроект: {proj}\nНовый старт: {_fmt(start)}\nНовый конец: {_fmt(end)}"
    await msg.answer(txt, reply_markup=_kb_yes_no())

# ---- confirm / apply ----
@router.callback_query(F.data == "ed:fix")
async def on_fix(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(EditDates.enter_name)
    await cb.message.answer("Ок, введи название проекта ещё раз:")

@router.callback_query(F.data == "ed:ok")
async def on_ok(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    d = await state.get_data()
    unit, proj = d["unit"], d["project"]
    s_new, e_new = d.get("new_start"), d.get("new_end")

    # индикатор загрузки
    stop = asyncio.Event()
    typing = asyncio.create_task(_typing(cb, stop))
    loading = await cb.message.answer("⏳ Применяю изменения…")

    try:
        if s_new and e_new:
            resp = await move_project(unit=unit, project=proj, new_start=s_new, new_end=e_new)
        else:
            resp = await extend_deadline(unit=unit, project=proj, new_end=e_new)

        if not resp or not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "unknown error")

        await loading.edit_text(f"✅ Готово\n{hbold(resp.get('unit') or unit)}\n• {proj}")
        await state.clear()
    except Exception as e:
        await loading.edit_text(f"⚠️ Ошибка: {hcode(str(e))}")
    finally:
        stop.set(); typing.cancel()
