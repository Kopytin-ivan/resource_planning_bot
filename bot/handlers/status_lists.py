# bot/handlers/status_lists.py
from __future__ import annotations

import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from ..gas_client import list_projects_by_status
from bot.utils.tg_utils import pretty_name, esc, loading_message, answer_html, edit_html, split_text


router = Router(name="status_lists")

_MAX = 3900

def _split_long(text: str) -> list[str]:
    # можно и импортный split_text использовать, оставлю локально чтобы не менять логику
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

def _format_block(title: str, items: list[dict]) -> str:
    if not items:
        return f"{title}\n— нет —"

    lines = [title]
    for it in items:
        unit = esc(it.get("unit") or "UNIT ?")
        sub  = esc(it.get("sub") or "")
        unit_show = f"{unit} / {sub}" if sub else unit

        name   = esc(pretty_name(it.get("name") or "—"))
        mgr    = esc(it.get("mgr") or "—")
        period = esc(it.get("period") or "—")
        end    = it.get("end")
        hasD   = bool(it.get("hasEndDate"))
        addEnd = (not hasD and end) and f" — до {esc(end)}" or ""

        lines.append(f"• {unit_show} — {name} — {mgr} — {period}{addEnd}")
    return "\n".join(lines)

@router.message(F.text.in_({"🟡 На согласовании/закрытие", "⏸ На паузе/не начат", "📋 Статусы проектов"}))
async def show_status_lists(msg: Message):
    # показываем лоадер в HTML
    async with loading_message(msg):
        resp = await list_projects_by_status()
    if not resp or not resp.get("ok"):
        await answer_html(msg, "⚠️ Не удалось получить статусы проектов.")
        return

    pending = resp.get("pending") or []
    paused  = resp.get("paused")  or []

    want = msg.text or ""
    if "📋" in want:
        head = hbold("Статусы проектов по всем юнитам")
        block = "\n\n".join([
            _format_block("🟡 На согласовании / закрытие:", pending),
            _format_block("⏸ На паузе / не начат:",        paused),
        ])
        text = f"{head}\n\n{block}"
        for part in _split_long(text):
            await answer_html(msg, part)
        return

    if "🟡" in want:
        text = _format_block(hbold("🟡 На согласовании / закрытие:"), pending)
        for part in _split_long(text):
            await answer_html(msg, part)
        return

    if "⏸" in want:
        text = _format_block(hbold("⏸ На паузе / не начат:"), paused)
        for part in _split_long(text):
            await answer_html(msg, part)
        return

# ====== Группировка с подюнитами (если используешь вторую версию) ======

_RX_SUB_CODE = re.compile(r"^\(\s*UNIT\s*([0-9]+(?:\.[0-9]+)?)\s*\)", re.I)

def _short_sub(label: str | None) -> str:
    if not label:
        return ""
    m = _RX_SUB_CODE.match(str(label))
    return m.group(1) if m else str(label)

def _format_grouped_by_unit(title: str, items: list[dict]) -> str:
    if not items:
        return f"{title}\n— нет —"
    by_unit: dict[str, list[dict]] = {}
    for it in items:
        by_unit.setdefault(it.get("unit") or "UNIT ?", []).append(it)

    lines = [title]
    for unit in sorted(by_unit.keys()):
        lines.append(hbold(esc(unit)))
        for it in by_unit[unit]:
            name   = esc(pretty_name(it.get("name") or "—"))
            mgr    = esc(it.get("mgr") or "—")
            period = esc(it.get("period") or "—")
            end    = it.get("end")
            hasD   = bool(it.get("hasEndDate"))
            addEnd = (not hasD and end) and f" — до {esc(end)}" or ""

            sub_label = it.get("sub") or ""
            sub = esc(_short_sub(sub_label))
            prefix = f"{sub} · " if sub else ""

            lines.append(f"• {prefix}{name} — {mgr} — {period}{addEnd}")
        lines.append("")
    return "\n".join(lines).rstrip()

async def _send_statuses(msg: Message, show: str):
    wait = await answer_html(msg, "⏳ Загрузка…")
    try:
        resp = await list_projects_by_status()
    except Exception as e:
        await edit_html(wait, f"⚠️ Не удалось получить статусы проектов.\n<code>{esc(str(e))}</code>")
        return

    if not resp or not resp.get("ok"):
        err = (resp or {}).get("error") or "неизвестная ошибка"
        await edit_html(wait, f"⚠️ Не удалось получить статусы проектов.\n<code>{esc(str(err))}</code>")
        return

    pending = resp.get("pending") or []
    paused  = resp.get("paused")  or []

    if show == "all":
        head = hbold("Статусы проектов по всем юнитам")
        block = "\n\n".join([
            _format_grouped_by_unit("🟡 На согласовании / закрытие:", pending),
            _format_grouped_by_unit("⏸ На паузе / не начат:",        paused),
        ])
        text = f"{head}\n\n{block}"
        parts = _split_long(text)
        await edit_html(wait, parts[0])
        for p in parts[1:]:
            await answer_html(msg, p)
        return

    if show == "pending":
        text = _format_grouped_by_unit(hbold("🟡 На согласовании / закрытие:"), pending)
        parts = _split_long(text)
        await edit_html(wait, parts[0])
        for p in parts[1:]:
            await answer_html(msg, p)
        return

    if show == "paused":
        text = _format_grouped_by_unit(hbold("⏸ На паузе / не начат:"), paused)
        parts = _split_long(text)
        await edit_html(wait, parts[0])
        for p in parts[1:]:
            await answer_html(msg, p)
        return

@router.message(F.text == "🟡 На согласовании/закрытие")
async def show_pending(msg: Message):
    await _send_statuses(msg, "pending")

@router.message(F.text == "⏸ На паузе/не начат")
async def show_paused(msg: Message):
    await _send_statuses(msg, "paused")

@router.message(F.text == "📋 Статусы проектов")
async def show_all_statuses(msg: Message):
    await _send_statuses(msg, "all")
