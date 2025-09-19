# bot/utils/tg_utils.py
from __future__ import annotations

import asyncio
import html
import re
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Awaitable, Callable

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery


# ========== текстовые утилиты ==========
_PREFIX_RE = re.compile(r'^\s*\d+(?:[–-]\d+){1,3}\s+')
_LINE_CODE_RE = re.compile(
    r'(?m)^(?:\s*[•\-·]\s*)?\d+(?:[–-]\d+){1,3}\s+(?=[A-Za-zА-Яа-я])'
)

def pretty_name(s: str) -> str:
    if not s:
        return ""
    return _PREFIX_RE.sub("", s).strip()

def esc(s: str) -> str:
    return html.escape(s or "")

def pn(s: str) -> str:
    """pretty+escape: для единичного имени проекта перед подстановкой в HTML."""
    return esc(pretty_name(s))

def strip_codes_in_text(text: str) -> str:
    return _LINE_CODE_RE.sub("", text)

def split_text(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in text.splitlines():
        add = len(line) + 1
        if cur_len + add > limit and cur:
            parts.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += add
    if cur:
        parts.append("\n".join(cur))
    return parts


# ========== отправка длинных сообщений ==========
async def reply_long(bot: Bot, chat_id: int, text: str):
    for chunk in split_text(text):
        await bot.send_message(chat_id, chunk)

async def reply_long_html(bot: Bot, chat_id: int, text: str):
    for chunk in split_text(text):
        await bot.send_message(chat_id, chunk, parse_mode=ParseMode.HTML)

async def answer_html(msg_or_call: Message | CallbackQuery, text: str, **kwargs):
    """Ответить сообщением в HTML-режиме (поддерживает reply_markup и др. kwargs)."""
    if isinstance(msg_or_call, CallbackQuery):
        return await msg_or_call.message.answer(text, parse_mode=ParseMode.HTML, **kwargs)
    return await msg_or_call.answer(text, parse_mode=ParseMode.HTML, **kwargs)

async def edit_html(message_or_cbq: Message | CallbackQuery, text: str, **kwargs):
    """Отредактировать текст сообщения в HTML-режиме (поддерживает reply_markup и др. kwargs)."""
    message = message_or_cbq.message if isinstance(message_or_cbq, CallbackQuery) else message_or_cbq
    return await message.edit_text(text, parse_mode=ParseMode.HTML, **kwargs)


# ========== временное «Загрузка…» ==========
@asynccontextmanager
async def loading_message(msg_or_call: Message | CallbackQuery, text: str = "⏳ Загрузка…"):
    """
    Показать временное сообщение «Загрузка…» (HTML) и убрать его после блока.
    Поддерживает Message и CallbackQuery.
    """
    if isinstance(msg_or_call, CallbackQuery):
        holder = await msg_or_call.message.answer(text, parse_mode=ParseMode.HTML)
    else:
        holder = await msg_or_call.answer(text, parse_mode=ParseMode.HTML)
    try:
        yield holder
    finally:
        try:
            await holder.delete()
        except Exception:
            pass


# ========== анти-даблклик / ограничение конкуренции ==========
_CHAT_LOCKS: dict[int, asyncio.Lock] = {}

# общий лимит одновременных запросов к GAS по всему боту
# подбери число под свои лимиты, обычно 2–4 достаточно
GAS_SEMAPHORE = asyncio.Semaphore(3)

def chat_lock(chat_id: int) -> asyncio.Lock:
    """Получить (или создать) лок для этого чата."""
    lock = _CHAT_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _CHAT_LOCKS[chat_id] = lock
    return lock

def _chat_id(evt: Message | CallbackQuery) -> int:
    return evt.chat.id if isinstance(evt, Message) else evt.message.chat.id

async def busy_reply(msg_or_cb: Message | CallbackQuery,
                     text: str = "⏳ Уже обрабатываю предыдущий запрос…"):
    """Короткий ответ на повторное нажатие, когда лок занят."""
    try:
        if isinstance(msg_or_cb, CallbackQuery):
            await msg_or_cb.answer(text, show_alert=False)
        else:
            await msg_or_cb.answer(text)
    except Exception:
        pass

def gas_guard(show_busy: bool = True):
    """
    Декоратор для хэндлеров, которые ходят в GAS:
      • Per-chat lock: повторные клики в этом чате игнорируются, пока идёт работа.
      • Global semaphore: ограничиваем общее число одновременных походов в GAS.
    Применение:
        @router.callback_query(...)
        @gas_guard()
        async def handler(cb: CallbackQuery, ...):
            ...
    """
    def deco(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(evt: Message | CallbackQuery, *args, **kwargs):
            lock = chat_lock(_chat_id(evt))
            if lock.locked():
                if show_busy:
                    await busy_reply(evt)
                return
            async with lock:
                async with GAS_SEMAPHORE:
                    return await fn(evt, *args, **kwargs)
        return wrapper
    return deco


__all__ = [
    # текст/HTML
    "pretty_name", "esc", "pn", "strip_codes_in_text", "split_text",
    "reply_long", "reply_long_html", "answer_html", "edit_html",
    "loading_message",
    # конкуренция
    "chat_lock", "busy_reply", "gas_guard", "GAS_SEMAPHORE",
]
