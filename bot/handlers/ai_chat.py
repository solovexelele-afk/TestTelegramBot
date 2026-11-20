"""ИИ-собеседник в личном чате: текст, фото, голосовые, кружки, стикеры → ответ «как друг»."""

from __future__ import annotations

import asyncio
import io
import logging
from collections import defaultdict
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, ReactionTypeEmoji
from aiogram.utils.chat_action import ChatActionSender

from bot import texts
from bot.config import Config
from bot.db import Database
from bot.handlers.draw import draw, image_intent
from bot.services.ai import AIError, AIService
from bot.services.messaging import bump, is_current, send_like_human
from bot.services.personas import (
    MIRROR_PERSONA,
    VOICE_NOTE,
    extract_reaction,
    extract_transcript,
    humanize,
    persona_prompt,
)

router = Router(name="ai_chat")
router.message.filter(F.chat.type == ChatType.PRIVATE)
logger = logging.getLogger(__name__)

MAX_MEDIA_BYTES = 15 * 1024 * 1024
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


@router.message(Command("reset"))
async def cmd_reset(message: Message, db: Database) -> None:
    bump(message.chat.id)
    await db.clear_dialog(f"u:{message.from_user.id}")
    await message.answer("🧹 всё, забыл. начинаем с чистого листа")


@router.callback_query(F.data == "ai:reset")
async def cb_reset(callback: CallbackQuery, db: Database) -> None:
    await db.clear_dialog(f"u:{callback.from_user.id}")
    await callback.answer("Диалог забыт 🧹")


async def _download(bot: Bot, file_id: str, size: int | None) -> bytes | None:
    if size and size > MAX_MEDIA_BYTES:
        return None
    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    return buf.getvalue()


async def _react(bot: Bot, message: Message, emoji: str | None) -> None:
    if not emoji:
        return
    with suppress(TelegramBadRequest):
        await bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji(emoji=emoji)])


async def _reply(
    message: Message,
    bot: Bot,
    db: Database,
    ai: AIService,
    config: Config,
    user_text: str,
    media: tuple[bytes, str] | None = None,
    voice: bool = False,
) -> None:
    chat_id, user_id = message.chat.id, message.from_user.id
    scope = f"u:{user_id}"
    gen = bump(chat_id)  # новое сообщение обрывает недосланный старый ответ
    if media is None:
        # текст сохраняем сразу: если человек пишет несколько сообщений подряд,
        # бот ответит один раз на всю пачку, ничего не потеряв
        await db.add_dialog(scope, "user", user_text)
    async with _locks[user_id]:
        if not is_current(chat_id, gen):
            if media is not None:
                await db.add_dialog(scope, "user", user_text)
            return
        user = await db.touch_user(user_id)
        history = await db.history(scope, config.history_limit)
        if media is not None:
            history.append(("user", user_text))
        profile, examples = "", None
        if user.persona == MIRROR_PERSONA:
            p = await db.style_profile(user_id)
            profile = p.text if p else ""
            examples = await db.style_examples(user_id)
        system = persona_prompt(user.persona, message.from_user.first_name, profile, examples)
        if voice:
            system += "\n\n" + VOICE_NOTE
        try:
            async with ChatActionSender.typing(bot=bot, chat_id=chat_id):
                answer = await ai.chat(system, history, media=media)
        except AIError as exc:
            logger.warning("AI error: %s", exc)
            await message.answer("бля, чет не догрузилось, скинь ещё раз" if media else texts.AI_FAIL)
            return

        if voice:
            transcript, answer = extract_transcript(answer)
            user_text = f"[голосовое] {transcript}" if transcript else user_text
        emoji, answer = extract_reaction(answer)
        parts = humanize(answer)
        if media is not None:
            await db.add_dialog(scope, "user", user_text)
        if not is_current(chat_id, gen):
            return  # пока ИИ думал, пришло новое сообщение — ответим уже на него
        await db.add_dialog(scope, "model", "\n".join(parts) or "👍")

    await _react(bot, message, emoji)
    await send_like_human(bot, chat_id, parts, gen=gen)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    prompt = image_intent(message.text)
    if prompt:
        await db.add_dialog(f"u:{message.from_user.id}", "user", message.text)
        await draw(bot, message.chat.id, message.from_user.id, prompt, ai, reply_to=message.message_id)
        return
    await _reply(message, bot, db, ai, config, message.text)


@router.message(F.photo)
async def on_photo(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    caption = message.caption or ""
    if caption and (prompt := image_intent(caption)):
        await draw(bot, message.chat.id, message.from_user.id, prompt, ai, reply_to=message.message_id)
        return
    if not ai.can_see:
        await message.answer("пока не могу смотреть фотки(")
        return
    photo = message.photo[-1]
    data = await _download(bot, photo.file_id, photo.file_size)
    if data is None:
        await message.answer("ого тяжёлая фотка, не открывается")
        return
    text = f"[прислал фото] {caption}".strip()
    await _reply(message, bot, db, ai, config, text, media=(data, "image/jpeg"))


@router.message(F.voice | F.video_note | F.audio)
async def on_voice(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    if not ai.can_see:
        await message.answer("гс пока не слушаю, напиши текстом)")
        return
    if message.voice:
        obj, mime, label = message.voice, "audio/ogg", "[голосовое]"
    elif message.video_note:
        obj, mime, label = message.video_note, "video/mp4", "[кружок]"
    else:
        obj, mime, label = message.audio, message.audio.mime_type or "audio/mpeg", "[аудио]"
    data = await _download(bot, obj.file_id, obj.file_size)
    if data is None:
        await message.answer("слишком длинное, не осилю ахах")
        return
    await _reply(message, bot, db, ai, config, label, media=(data, mime), voice=True)


@router.message(F.sticker)
async def on_sticker(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    emoji = message.sticker.emoji or ""
    await _reply(message, bot, db, ai, config, f"[стикер {emoji}]".strip())


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer("🤔 не знаю такую команду. список — /help")


@router.message()
async def non_text(message: Message) -> None:
    await message.answer(texts.NON_TEXT)
