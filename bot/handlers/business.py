"""Telegram Business: автоответчик в личке владельца аккаунта (нужен Telegram Premium)."""

from __future__ import annotations

import logging
import time
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BusinessConnection, CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.config import Config
from bot.db import Database
from bot.handlers.ai_chat import send_like_human
from bot.services.ai import AIError, AIService
from bot.services.personas import business_prompt, humanize

router = Router(name="business")
logger = logging.getLogger(__name__)

AWAY_REPEAT_SEC = 3 * 60 * 60  # шаблон в один чат — не чаще раза в 3 часа
PAUSE_OPTIONS = [0, 5, 15, 30, 60]
_away_sent: dict[tuple[str, int], float] = {}


class BizState(StatesGroup):
    away_text = State()
    instructions = State()


def _can_reply(conn: BusinessConnection) -> bool:
    rights = getattr(conn, "rights", None)
    if rights is not None and getattr(rights, "can_reply", None) is not None:
        return bool(rights.can_reply)
    return bool(getattr(conn, "can_reply", True))


# ---------- подключение / отключение ----------
@router.business_connection()
async def on_connection(conn: BusinessConnection, bot: Bot, db: Database) -> None:
    b = await db.upsert_business(conn.id, conn.user.id, conn.user.first_name, conn.is_enabled, _can_reply(conn))
    logger.info("Business connection %s: owner=%s enabled=%s", conn.id, conn.user.id, conn.is_enabled)
    with suppress(TelegramBadRequest, TelegramForbiddenError):
        if conn.is_enabled:
            await bot.send_message(
                conn.user_chat_id,
                "✅ Бот подключён к вашему аккаунту через Telegram Business!\n\n" + texts.business_status(b),
                reply_markup=kb.business_inline(b.mode, b.pause_minutes),
            )
        else:
            await bot.send_message(conn.user_chat_id, "⏏️ Автоответчик отключён от вашего аккаунта.")


# ---------- входящие сообщения в личке владельца ----------
@router.business_message()
async def on_business_message(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    conn_id = message.business_connection_id
    b = await db.business(conn_id)
    if b is None:
        # подключение было до перезапуска (без БД) — восстановим из Telegram
        try:
            conn = await bot.get_business_connection(conn_id)
        except TelegramBadRequest:
            return
        b = await db.upsert_business(conn.id, conn.user.id, conn.user.first_name, conn.is_enabled, _can_reply(conn))

    if getattr(message, "sender_business_bot", None):
        return  # это наше собственное сообщение от имени владельца
    if message.from_user and message.from_user.id == b.owner_id:
        await db.mark_owner_active(conn_id, message.chat.id)
        return
    if not b.enabled or not b.can_reply or b.mode == "off" or message.chat.type != ChatType.PRIVATE:
        return
    if await db.owner_recently_active(conn_id, message.chat.id, b.pause_minutes):
        return

    if b.mode == "away":
        key = (conn_id, message.chat.id)
        if time.monotonic() - _away_sent.get(key, -AWAY_REPEAT_SEC) < AWAY_REPEAT_SEC:
            return
        _away_sent[key] = time.monotonic()
        await bot.send_message(message.chat.id, b.away_text, business_connection_id=conn_id, parse_mode=None)
        return

    # mode == "ai"
    text = message.text or message.caption
    if not text:
        return
    scope = f"b:{conn_id}:{message.chat.id}"
    sender = message.from_user.first_name if message.from_user else "Собеседник"
    await db.add_dialog(scope, "user", f"{sender}: {text}", keep=40)
    history = await db.history(scope, config.history_limit)
    try:
        with suppress(TelegramBadRequest):
            await bot.send_chat_action(message.chat.id, "typing", business_connection_id=conn_id)
        answer = await ai.chat(business_prompt(b.owner_name, b.instructions), history, max_tokens=500)
    except AIError:
        return
    parts = humanize(answer, max_parts=3)
    await db.add_dialog(scope, "model", "\n".join(parts), keep=40)
    await send_like_human(bot, message.chat.id, parts, business_connection_id=conn_id)


# ---------- настройки в личке с ботом ----------
async def _show(target: Message, db: Database, user_id: int, edit: bool = False) -> None:
    b = await db.business_by_owner(user_id)
    markup = kb.business_inline(b.mode, b.pause_minutes) if b else kb.back_inline()
    if edit:
        with suppress(TelegramBadRequest):
            await target.edit_text(texts.business_status(b), reply_markup=markup)
    else:
        await target.answer(texts.business_status(b), reply_markup=markup)


@router.message(F.chat.type == ChatType.PRIVATE, Command("business"))
@router.message(F.chat.type == ChatType.PRIVATE, F.text == kb.BTN_BUSINESS)
async def cmd_business(message: Message, db: Database) -> None:
    await _show(message, db, message.from_user.id)


@router.callback_query(F.data == "menu:business")
async def cb_business(callback: CallbackQuery, db: Database) -> None:
    await _show(callback.message, db, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("biz:"))
async def cb_biz(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    b = await db.business_by_owner(callback.from_user.id)
    if b is None:
        await callback.answer("Сначала подключите бота в Telegram Business", show_alert=True)
        return
    action = callback.data.split(":")[1:]
    if action[0] == "mode" and len(action) == 2 and action[1] in {"ai", "away", "off"}:
        await db.update_business(b.id, mode=action[1])
        await callback.answer("Режим сохранён")
    elif action[0] == "pause":
        nxt = PAUSE_OPTIONS[(PAUSE_OPTIONS.index(b.pause_minutes) + 1) % len(PAUSE_OPTIONS)] if b.pause_minutes in PAUSE_OPTIONS else 15
        await db.update_business(b.id, pause_minutes=nxt)
        await callback.answer(f"Пауза: {nxt} мин")
    elif action[0] == "away_text":
        await state.set_state(BizState.away_text)
        await callback.message.answer("✏️ Пришлите текст шаблона одним сообщением.", reply_markup=kb.cancel_inline())
        await callback.answer()
        return
    elif action[0] == "instructions":
        await state.set_state(BizState.instructions)
        await callback.message.answer(
            "🧾 Напишите, как ИИ должен отвечать за вас. Например:\n"
            "<i>Я учусь до 18:00, по работе пишите на почту, общайся на «ты» и коротко.</i>\n\n"
            "Отправьте «-», чтобы очистить.",
            reply_markup=kb.cancel_inline(),
        )
        await callback.answer()
        return
    else:
        await callback.answer()
        return
    await _show(callback.message, db, callback.from_user.id, edit=True)


@router.message(BizState.away_text, F.text)
async def set_away(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    if b := await db.business_by_owner(message.from_user.id):
        await db.update_business(b.id, away_text=message.text[:1000])
    await message.answer("✅ Шаблон сохранён")
    await _show(message, db, message.from_user.id)


@router.message(BizState.instructions, F.text)
async def set_instructions(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    value = "" if message.text.strip() == "-" else message.text[:1500]
    if b := await db.business_by_owner(message.from_user.id):
        await db.update_business(b.id, instructions=value)
    await message.answer("✅ Инструкции сохранены")
    await _show(message, db, message.from_user.id)
