"""ИИ-собеседник в личном чате: любой текст → ответ с памятью диалога."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from bot import texts
from bot.config import Config
from bot.db import Database
from bot.services.ai import AIError, AIService
from bot.services.personas import humanize, persona_prompt

router = Router(name="ai_chat")
router.message.filter(F.chat.type == ChatType.PRIVATE)
logger = logging.getLogger(__name__)

COOLDOWN_SEC = 1.5
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_last_call: dict[int, float] = {}

TG_LIMIT = 4000


def split_text(text: str, limit: int = TG_LIMIT) -> list[str]:
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


@router.message(Command("reset"))
async def cmd_reset(message: Message, db: Database) -> None:
    await db.clear_dialog(f"u:{message.from_user.id}")
    await message.answer("🧹 Готово, начинаем с чистого листа!")


@router.callback_query(F.data == "ai:reset")
async def cb_reset(callback: CallbackQuery, db: Database) -> None:
    await db.clear_dialog(f"u:{callback.from_user.id}")
    await callback.answer("Диалог забыт 🧹", show_alert=False)


@router.message(F.text & ~F.text.startswith("/"))
async def chat(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    user_id = message.from_user.id
    now = time.monotonic()
    if now - _last_call.get(user_id, 0) < COOLDOWN_SEC:
        await asyncio.sleep(COOLDOWN_SEC)
    _last_call[user_id] = time.monotonic()

    async with _locks[user_id]:
        user = await db.touch_user(user_id)
        scope = f"u:{user_id}"
        await db.add_dialog(scope, "user", message.text)
        history = await db.history(scope, config.history_limit)
        try:
            async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
                answer = await ai.chat(persona_prompt(user.persona, message.from_user.first_name), history)
        except AIError:
            await message.answer(texts.AI_FAIL)
            return
        parts = humanize(answer)
        # в историю — уже «очеловеченный» текст, чтобы модель держала стиль
        await db.add_dialog(scope, "model", "\n".join(parts))

    await send_like_human(bot, message.chat.id, parts)


async def send_like_human(bot: Bot, chat_id: int, parts: list[str], **kwargs) -> None:
    """Шлёт несколько коротких сообщений подряд с «печатает…» между ними, как живой человек."""
    for i, part in enumerate(parts):
        if i:
            with suppress(Exception):
                await bot.send_chat_action(chat_id, "typing", **kwargs)
            await asyncio.sleep(min(0.6 + len(part) * 0.03, 2.5))
        for chunk in split_text(part):
            await bot.send_message(chat_id, chunk, parse_mode=None, **kwargs)


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer("🤔 Не знаю такой команды. Список — /help")


@router.message()
async def non_text(message: Message) -> None:
    await message.answer(texts.NON_TEXT)
