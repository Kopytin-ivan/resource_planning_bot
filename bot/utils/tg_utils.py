# bot/utils/tg_utils.py
from aiogram import Bot

def split_text(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, cur, cur_len = [], [], 0
    for line in text.splitlines():
        add = len(line) + 1
        if cur_len + add > limit and cur:
            parts.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(line); cur_len += add
    if cur:
        parts.append("\n".join(cur))
    return parts

async def reply_long(bot: Bot, chat_id: int, text: str):
    for chunk in split_text(text):
        await bot.send_message(chat_id, chunk)
