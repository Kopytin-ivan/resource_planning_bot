# bot/handlers/status_lists.py
from __future__ import annotations

import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from ..gas_client import list_projects_by_status

router = Router(name="status_lists")

_MAX = 3900  # запас до лимита 4096

def _split_long(text: str) -> list[str]:
    parts, buf, ln = [], [], 0
    for line in text.splitlines():
        add = len(line) + 1
        if ln + add > _MAX:
            parts.append("\n".join(buf))
            buf, ln = [line], add
        else:
            buf.append(line); ln += add
    if buf:
        parts.append("\n".join(buf))
    return parts

_RX_SUB_CODE = re.compile(r"^\(\s*UNIT\s*([0-9]+(?:\.[0-9]+)?)\s*\)", re.I)

def _short_sub(label: str | None) -> str:
    """Из '(UNIT 2.1) Иван Иванов' вытащим '2.1'. Если не распознали — вернём исходник."""
    if not label:
        return ""
    m = _RX_SUB_CODE.match(str(label))
    return m.group(1) if m else str(label)

def _format_grouped_by_unit(title: str, items: list[dict]) -> str:
    if not items:
        return f"{title}\n— нет —"
    # сгруппируем по верхнему юниту
    by_unit: dict[str, list[dict]] = {}
    for it in items:
        by_unit.setdefault(it.get("unit") or "UNIT ?", []).append(it)

    lines = [title]
    for unit in sorted(by_unit.keys()):
        lines.append(hbold(unit))
        for it in by_unit[unit]:
            name   = it.get("name") or "—"
            mgr    = it.get("mgr") or "—"
            period = it.get("period") or "—"
            end    = it.get("end")
            hasD   = bool(it.get("hasEndDate"))
            addEnd = (not hasD and end) and f" — до {end}" or ""

            # новенькое: подюнит, если есть
            sub_label = it.get("sub") or ""
            sub = _short_sub(sub_label)
            sub_prefix = f"{sub} · " if sub else ""

            lines.append(f"• {sub_prefix}{name} — {mgr} — {period}{addEnd}")
        lines.append("")  # пустая строка между юнитами
    return "\n".join(lines).rstrip()

async def _send_statuses(msg: Message, show: str):
    # 1) сразу показываем «Загрузка…»
    wait = await msg.answer("⏳ Загрузка…")

    try:
        resp = await list_projects_by_status()
    except Exception as e:
        await wait.edit_text(f"⚠️ Не удалось получить статусы проектов.\n<code>{e}</code>")
        return

    if not resp or not resp.get("ok"):
        err = (resp or {}).get("error") or "неизвестная ошибка"
        await wait.edit_text(f"⚠️ Не удалось получить статусы проектов.\n<code>{err}</code>")
        return

    pending = resp.get("pending") or []
    paused  = resp.get("paused")  or []

    if show == "all":
        head = hbold("Статусы проектов по всем юнитам")
        block = "\n\n".join([
            _format_grouped_by_unit("🟡 На согласовании / закрытие:", pending),
            _format_grouped_by_unit("⏸ На паузе / не начат:", paused),
        ])
        text = f"{head}\n\n{block}"
        parts = _split_long(text)
        # первый кусок — редактируем «Загрузка…», остальные — докидываем отдельными сообщениями
        await wait.edit_text(parts[0])
        for p in parts[1:]:
            await msg.answer(p)
        return

    if show == "pending":
        text = _format_grouped_by_unit(hbold("🟡 На согласовании / закрытие:"), pending)
        parts = _split_long(text)
        await wait.edit_text(parts[0])
        for p in parts[1:]:
            await msg.answer(p)
        return

    if show == "paused":
        text = _format_grouped_by_unit(hbold("⏸ На паузе / не начат:"), paused)
        parts = _split_long(text)
        await wait.edit_text(parts[0])
        for p in parts[1:]:
            await msg.answer(p)
        return

# Кнопки из твоего extra_menu
@router.message(F.text == "🟡 На согласовании/закрытие")
async def show_pending(msg: Message):
    await _send_statuses(msg, "pending")

@router.message(F.text == "⏸ На паузе/не начат")
async def show_paused(msg: Message):
    await _send_statuses(msg, "paused")

# (опционально) одна общая кнопка — если заведёшь её в меню
@router.message(F.text == "📋 Статусы проектов")
async def show_all_statuses(msg: Message):
    await _send_statuses(msg, "all")
