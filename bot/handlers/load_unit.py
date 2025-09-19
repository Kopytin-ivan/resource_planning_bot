# bot/handlers/load_unit.py
from __future__ import annotations

import os, json, tempfile, time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.markdown import hbold

from ..gas_client import list_units_min, list_active_projects
from ..keyboards.units import units_keyboard
from ..keyboards.periods import periods_kb
from ..utils.tg_utils import (
    split_text,
    strip_codes_in_text,
    loading_message,
    pn,
    answer_html,
    edit_html,
    gas_guard,
)

router = Router(name="unit_load")

# ---- простейший кэш в памяти процесса бота ----
_UNITS_CACHE: list[dict] | None = None
_UNITS_TS: float = 0.0
_UNITS_TTL = 300  # 5 минут

# персистентный кэш на диск — чтобы даже при перезапуске не дергать GAS
_CACHE_FILE = os.path.join(tempfile.gettempdir(), "bot_units_cache_v2.json")
_PERSIST_TTL = 3600  # 1 час


async def _get_all_units(force_refresh: bool = False) -> list[dict]:
    """
    ВНИМАНИЕ: это помощник, НЕ хэндлер. Не вешаем @gas_guard здесь.
    Ограничение конкуренции и «Загрузка…» ставим в вызывающих местах.
    """
    global _UNITS_CACHE, _UNITS_TS
    now = time.time()

    # 1) кэш в памяти процесса
    if not force_refresh and _UNITS_CACHE and (now - _UNITS_TS) < _UNITS_TTL:
        return _UNITS_CACHE

    # 2) кэш на диске
    if not force_refresh and os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (now - float(data.get("ts", 0))) < _PERSIST_TTL and isinstance(data.get("units"), list):
                _UNITS_CACHE = data["units"]
                _UNITS_TS = now
                return _UNITS_CACHE
        except Exception:
            pass  # игнорим битый файл

    # 3) запрос к GAS
    resp = await list_units_min()
    if not (resp and resp.get("ok")):
        raise RuntimeError((resp or {}).get("error") or "Не удалось получить список юнитов")

    units = resp.get("units") or []
    for u in units:
        if not u.get("label"):
            u["label"] = f"(UNIT {u.get('code')})"

    _UNITS_CACHE = units
    _UNITS_TS = now

    # 4) сохраняем на диск
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": now, "units": units}, f, ensure_ascii=False)
    except Exception:
        pass

    return units


def _top_units(units: list[dict]) -> list[dict]:
    return [u for u in units if "." not in str(u.get("code", ""))]


def _sub_units(units: list[dict], top_code: str) -> list[dict]:
    pref = f"{top_code}."
    return [u for u in units if str(u.get("code", "")).startswith(pref)]


async def _show_sub_units(cb: CallbackQuery, top_code: str, page: int = 1):
    async with loading_message(cb, "⏳ Загружаю под-юниты…"):
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
    Обязательно показываем лоадер, т.к. это вызов к GAS.
    """
    try:
        async with loading_message(cb, "⏳ Загружаю актуальные проекты…"):
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
            cleaned = strip_codes_in_text(ch)
            for part in split_text(cleaned, limit=3900):
                await answer_html(cb, part)  # HTML, чтобы <b> работал
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


async def _show_top_units(msg_or_cb: Message | CallbackQuery, page: int = 1):
    loading_txt = "⏳ Загружаю отделы…"
    try:
        if isinstance(msg_or_cb, CallbackQuery):
            # для инлайн-кейса редактируем текущее сообщение → покажем лоадер
            await msg_or_cb.answer()
            await msg_or_cb.message.edit_text(loading_txt)
            units = await _get_all_units()
            tops = _top_units(units)
            kb = units_keyboard(
                tops,
                page=page,
                action_prefix="unitload_top",
                extra_rows=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="unitload_refresh")]],
            )
            await msg_or_cb.message.edit_text(hbold("Выберите отдел:"), reply_markup=kb)
        else:
            # для message сначала шлём плейсхолдер «⏳», потом редактируем его же
            holder = await msg_or_cb.answer(loading_txt)
            units = await _get_all_units()
            tops = _top_units(units)
            kb = units_keyboard(
                tops,
                page=page,
                action_prefix="unitload_top",
                extra_rows=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="unitload_refresh")]],
            )
            await holder.edit_text(hbold("Выберите отдел:"), reply_markup=kb)
    except Exception as e:
        text_err = f"⚠️ Ошибка при загрузке отделов: {e!s}"
        if isinstance(msg_or_cb, CallbackQuery):
            try:
                await msg_or_cb.message.edit_text(text_err)
            except Exception:
                await msg_or_cb.message.answer(text_err)
        else:
            try:
                await holder.edit_text(text_err)
            except Exception:
                await msg_or_cb.answer(text_err)

# --- callbacks -------------------------------------------------------

@router.message(F.text == "🧩 Загруженность юнита")
@gas_guard()   
async def on_unit_load_entry(msg: Message):
    await _show_top_units(msg, page=1)


@router.callback_query(F.data == "unitload_refresh")
@gas_guard()
async def on_unitload_refresh(cb: CallbackQuery):
    await cb.answer("Обновляю список…")
    global _UNITS_CACHE, _UNITS_TS
    _UNITS_CACHE, _UNITS_TS = None, 0.0
    try:
        os.remove(_CACHE_FILE)
    except OSError:
        pass
    await _show_top_units(cb, page=1)


@router.callback_query(F.data == "unitload_top")
@gas_guard()
async def on_unitload_top(cb: CallbackQuery):
    await cb.answer()
    await _show_top_units(cb, page=1)


@router.callback_query(F.data.startswith("unitload_top:page:"))
@gas_guard()
async def on_unitload_top_page(cb: CallbackQuery):
    await cb.answer()
    try:
        page = int((cb.data or "").split(":")[-1])
    except Exception:
        page = 1
    await _show_top_units(cb, page=page)


@router.callback_query(F.data.startswith("unitload_top:pick:"))
@gas_guard()
async def on_unitload_top_pick(cb: CallbackQuery):
    await cb.answer()
    # ⏳ этот вызов может дернуть GAS (если кэш холодный) — показываем лоадер
    async with loading_message(cb, "⏳ Загружаю отдел…"):
        units = await _get_all_units()
    code = (cb.data or "").split(":")[-1]
    subs = _sub_units(units, code)
    if subs:
        await _show_sub_units(cb, top_code=code, page=1)
        return
    # отдел без под-юнитов → сразу актуальные + клавиатура завершений
    await _send_active_preview(cb, code)
    label = next((u.get("label") for u in units if str(u.get("code")) == str(code)), None)
    await _ask_endings_period(cb, code=code, label=label)


@router.callback_query(F.data.startswith("unitload_sub:"))
@gas_guard()
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
        # НЕ дергаем GAS ради лейбла: используем кэш, иначе дефолт.
        label = next(
            (u.get("label") for u in (_UNITS_CACHE or []) if str(u.get("code")) == str(code)),
            f"(UNIT {code})"
        )
        await _ask_endings_period(cb, code=code, label=label)
        return


@router.callback_query(F.data.startswith("unitload_show:"))
@gas_guard()
async def on_unitload_show_dept(cb: CallbackQuery):
    await cb.answer()
    code = (cb.data or "").split(":")[-1]
    await _send_active_preview(cb, code)
    # Для подписи снова НЕ ходим в GAS — берём лейбл из кэша или дефолт
    label = next(
        (u.get("label") for u in (_UNITS_CACHE or []) if str(u.get("code")) == str(code)),
        f"(UNIT {code})"
    )
    await _ask_endings_period(cb, code=code, label=label)
