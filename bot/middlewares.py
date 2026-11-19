"""Middleware: логирование входящих апдейтов."""

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger("bot.updates")


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        if isinstance(event, Message):
            logger.info("message from %s: %r", event.from_user and event.from_user.id, event.text)
        elif isinstance(event, CallbackQuery):
            logger.info("callback from %s: %r", event.from_user.id, event.data)
        try:
            return await handler(event, data)
        finally:
            logger.debug("handled in %.1f ms", (time.perf_counter() - started) * 1000)
