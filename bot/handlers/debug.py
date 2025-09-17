# bot/handlers/debug.py
import logging
from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query()
async def catch_all_callbacks(cb: CallbackQuery):
    # Логируем любые callback_data, чтобы понимать — приходят ли клики
    logging.info("CallbackQuery: data=%r from chat=%s", cb.data, cb.message.chat.id if cb.message else None)
    # Ничего не меняем в сообщении, просто подтверждаем клик
    await cb.answer()
