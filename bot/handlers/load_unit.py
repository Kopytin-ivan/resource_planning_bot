# bot/handlers/load_unit.py
from __future__ import annotations

import time
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.markdown import hbold

from ..gas_client import list_units_min, list_active_projects
from ..keyboards.units import units_keyboard
from ..keyboards.periods import periods_kb
from ..utils.tg_utils import split_text

router = Router(name="unit_load")

# ---- простейший кэш в памяти процесса бота ----
_UNITS_CACHE: list[dict] | None = None
_UNITS_TS: float = 0.0
_UNITS_TTL = 300  # 5 минут


async def _get_all_units(force_refresh: bool = False) -> list[dict]:
    global _UNITS_CACHE, _UNITS_TS
    now = time.time()
    if not force_refresh and _UNITS_CACHE and (now - _UNITS_TS) < _UNITS_TTL:
        return _UNITS_CACHE

    resp = await list_units_min()
    if not (resp and resp.get("ok")):
        raise RuntimeError(resp.get("error") or "Не удалось получить список юнитов")

    units = resp.get("units") or []
    for u in units:
        if not u.get("label"):
            u["label"] = f"(UNIT {u.get('code')})"
    _UNITS_CACHE = units
    _UNITS_TS = now
    return units


def _top_units(units: list[dict]) -> list[dict]:
    return [u for u in units if "." not in str(u.get("code", ""))]


def _sub_units(units: list[dict], top_code: str) -> list[dict]:
    pref = f"{top_code}."
    return [u for u in units if str(u.get("code", "")).startswith(pref)]


async def _show_top_units(cb: CallbackQuery, page: int = 1):
    units = await _get_all_units()
    tops = _top_units(units)
    kb = units_keyboard(
        tops,
        page=page,
        action_prefix="unitload_top",
        extra_rows=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="unitload_refresh")]],
    )
    await cb.message.edit_text(hbold("Выберите отдел:"), reply_markup=kb)


async def _show_sub_units(cb: CallbackQuery, top_code: str, page: int = 1):
    units = await _get_all_units()
    subs = _sub_units(units, top_code)
    dept_label = next((u.get("label") for u in units if str(u.get("code")) == str(top_code)), f"(UNIT {top_code})")

    extra = [
        [InlineKeyboardButton(text="📊 Показать отдел целиком", callback_data=f"unitload_show:{top_code}")],
        [InlineKeyboardButton(text="⬅️ К отделам", callback_data="unitload_top")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="unitload_refresh")],
    ]
    kb = units_keyboard(subs, page=page, action_prefix=f"unitload_sub:{top_code}", extra_rows=extra)
    await cb.message.edit_text(f"{hbold(dept_label)}\nВыберите под-юнит:", reply_markup=kb)


async def _send_active_preview(cb: CallbackQuery, code: str):
    """
    Шлёт список актуальных (не завершённых) проектов выбранного юнита.
    ВАЖНО: не вызываем cb.answer() здесь — handlers уже ответили на callback.
    """
    try:
        resp = await list_active_projects(code)
        if not resp or not resp.get("ok"):
            err = (resp or {}).get("error") or "неизвестная ошибка"
            await cb.message.answer(f"⚠️ Не удалось получить проекты для UNIT {code}: {err}")
            return

        chunks = resp.get("chunks") or []
        if not chunks:
            await cb.message.answer(f"🧩 (UNIT {code})\nАктуальных проектов нет.")
            return

        for ch in chunks:
            for part in split_text(ch, limit=3900):
                await cb.message.answer(part)

    except Exception as e:
        await cb.message.answer(f"⚠️ Ошибка при загрузке проектов UNIT {code}: {e!s}")


async def _ask_endings_period(cb: CallbackQuery, code: str, label: str | None = None):
    """
    Показываем клавиатуру выбора периода именно для 'завершений' выбранного юнита.
    scope используем endings__<код>, чтобы period_select отправил запросы завершений, а не load_all.
    """
    await cb.message.answer(
        f"{label or f'(UNIT {code})'}\nПоказать проекты, которые завершатся…",
        reply_markup=periods_kb(scope=f"endings__{code}")
    )


# --- callbacks -------------------------------------------------------

@router.callback_query(F.data == "unitload_refresh")
async def on_unitload_refresh(cb: CallbackQuery):
    await cb.answer("Обновляю список…")
    global _UNITS_CACHE, _UNITS_TS
    _UNITS_CACHE, _UNITS_TS = None, 0.0
    await _show_top_units(cb, page=1)


@router.callback_query(F.data == "unitload_top")
async def on_unitload_top(cb: CallbackQuery):
    await cb.answer()
    await _show_top_units(cb, page=1)


@router.callback_query(F.data.startswith("unitload_top:page:"))
async def on_unitload_top_page(cb: CallbackQuery):
    await cb.answer()
    try:
        page = int((cb.data or "").split(":")[-1])
    except Exception:
        page = 1
    await _show_top_units(cb, page=page)


@router.callback_query(F.data.startswith("unitload_top:pick:"))
async def on_unitload_top_pick(cb: CallbackQuery):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    units = await _get_all_units()
    subs = _sub_units(units, code)
    if subs:
        await _show_sub_units(cb, top_code=code, page=1)
        return
    # отдел без под-юнитов → сразу актуальные + клавиатура завершений
    await _send_active_preview(cb, code)
    label = next((u.get("label") for u in units if str(u.get("code")) == str(code)), None)
    await _ask_endings_period(cb, code=code, label=label)


@router.callback_query(F.data.startswith("unitload_sub:"))
async def on_unitload_sub(cb: CallbackQuery):
    await cb.answer()
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        return
    top_code = parts[1]
    action = parts[2]
    if action == "page":
        try:
            page = int(parts[3])
        except Exception:
            page = 1
        await _show_sub_units(cb, top_code=top_code, page=page)
        return
    if action == "pick":
        code = parts[3]
        await _send_active_preview(cb, code)  # ← список актуальных
        # затем — клавиатура завершений для выбранного под-юнита
        units = await _get_all_units()
        label = next((u.get("label") for u in units if str(u.get("code")) == str(code)), None)
        await _ask_endings_period(cb, code=code, label=label)
        return


@router.callback_query(F.data.startswith("unitload_show:"))
async def on_unitload_show_dept(cb: CallbackQuery):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    await _send_active_preview(cb, code)
    units = await _get_all_units()
    label = next((u.get("label") for u in units if str(u.get("code")) == str(code)), None)
    await _ask_endings_period(cb, code=code, label=label)
