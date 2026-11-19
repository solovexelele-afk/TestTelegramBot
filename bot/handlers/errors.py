"""Глобальный обработчик ошибок."""

import logging
from contextlib import suppress

from aiogram import Router
from aiogram.types import ErrorEvent

from bot import texts

router = Router(name="errors")
logger = logging.getLogger(__name__)


@router.error()
async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)

    update = event.update
    with suppress(Exception):
        if update.message:
            await update.message.answer(texts.ERROR_TEXT)
        elif update.callback_query:
            await update.callback_query.answer(texts.ERROR_TEXT, show_alert=True)
    return True
