"""Отправка ответов «как живой человек» + отмена устаревших ответов.

Если ИИ отвечает несколькими сообщениями с паузами, а пользователь за это время написал новое
сообщение или команду (например /img), недосланный «хвост» старого ответа отменяется.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress

from aiogram import Bot

TG_LIMIT = 4000

# номер «поколения» диалога для каждого чата: растёт при каждом новом сообщении пользователя
_generation: defaultdict[int, int] = defaultdict(int)


def bump(chat_id: int) -> int:
    """Отмечает новое сообщение в чате и возвращает его номер."""
    _generation[chat_id] += 1
    return _generation[chat_id]


def is_current(chat_id: int, gen: int) -> bool:
    return _generation[chat_id] == gen


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


async def send_like_human(
    bot: Bot, chat_id: int, parts: list[str], gen: int | None = None, **kwargs
) -> int:
    """Шлёт короткие сообщения подряд с «печатает…» между ними. Возвращает, сколько отправлено.

    gen — номер поколения: если пользователь успел написать что-то новое, остаток не отправляется.
    """
    sent = 0
    for i, part in enumerate(parts):
        if gen is not None and not is_current(chat_id, gen):
            break
        if i:
            with suppress(Exception):
                await bot.send_chat_action(chat_id, "typing", **kwargs)
            await asyncio.sleep(min(0.6 + len(part) * 0.03, 2.5))
            if gen is not None and not is_current(chat_id, gen):
                break
        for chunk in split_text(part):
            await bot.send_message(chat_id, chunk, parse_mode=None, **kwargs)
        sent += 1
    return sent
