"""Групповые чаты: приветствие, антиспам, предупреждения, модерация, розыгрыши, статистика, ИИ."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict, deque
from contextlib import suppress
from datetime import timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType, MessageEntityType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, ChatPermissions, Message, User

from bot import keyboards as kb
from bot.config import Config
from bot.db import Database
from bot.services.messaging import send_like_human
from bot.services.ai import AIError, AIService
from bot.services.personas import GROUP_PROMPT, humanize

router = Router(name="group")
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
logger = logging.getLogger(__name__)

FLOOD_MESSAGES = 6
FLOOD_WINDOW_SEC = 10
FLOOD_MUTE_MIN = 5
WARN_MUTE_MIN = 60
LINK_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/)", re.IGNORECASE)

_flood: defaultdict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=FLOOD_MESSAGES))
_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}

NO_PERMS = ChatPermissions(can_send_messages=False)
ALL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def mention(user: User) -> str:
    return f'<a href="tg://user?id={user.id}">{escape(user.first_name)}</a>'


async def is_admin(bot: Bot, chat_id: int, user_id: int, config: Config | None = None) -> bool:
    if config and user_id in config.admin_ids:
        return True
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    if cached and time.monotonic() - cached[1] < 60:
        return cached[0]
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}
    except TelegramBadRequest:
        result = False
    _admin_cache[key] = (result, time.monotonic())
    return result


async def _require_admin(message: Message, bot: Bot, config: Config) -> bool:
    # Сообщения от имени группы/канала (анонимный админ) — sender_chat == сам чат.
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if message.from_user and await is_admin(bot, message.chat.id, message.from_user.id, config):
        return True
    await message.reply("⛔ Эта команда только для администраторов.")
    return False


async def _target(message: Message) -> User | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    await message.reply("↩️ Ответьте этой командой на сообщение нужного участника.")
    return None


async def _safe(coro, message: Message) -> bool:
    try:
        await coro
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning("Модерация не удалась: %s", exc)
        await message.reply("⚠️ Не хватает прав. Сделайте меня администратором с правом блокировки и удаления.")
        return False


# ---------- новые участники ----------
@router.message(F.new_chat_members)
async def on_join(message: Message, bot: Bot, db: Database) -> None:
    me = await bot.me()
    settings = await db.group(message.chat.id)
    for user in message.new_chat_members:
        if user.id == me.id:
            await message.answer(
                "👋 Всем привет! Я помогу с порядком в чате и поболтаю, если позовёте.\n\n"
                "Чтобы всё работало, сделайте меня <b>администратором</b> "
                "(удаление сообщений, блокировка). Настройки — /settings, помощь — /help."
            )
        elif settings.welcome and not user.is_bot:
            await message.answer(
                f"👋 Добро пожаловать, {mention(user)}! Рады видеть в «{escape(message.chat.title or 'чате')}». "
                "Ведите себя хорошо 🙂"
            )


# ---------- команды ----------
@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot, db: Database, config: Config) -> None:
    if not await _require_admin(message, bot, config):
        return
    g = await db.group(message.chat.id)
    await message.answer("⚙️ <b>Настройки чата</b>", reply_markup=kb.group_settings_inline(g))


@router.callback_query(F.data.startswith("gs:"))
async def cb_settings(callback: CallbackQuery, bot: Bot, db: Database, config: Config) -> None:
    if not await is_admin(bot, callback.message.chat.id, callback.from_user.id, config):
        await callback.answer("Только для администраторов", show_alert=True)
        return
    field_name = callback.data.split(":", 1)[1]
    if field_name not in {"welcome", "antilink", "antiflood", "ai_reply"}:
        await callback.answer()
        return
    g = await db.toggle_group(callback.message.chat.id, field_name)
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=kb.group_settings_inline(g))
    await callback.answer("Сохранено")


@router.message(Command("warn"))
async def cmd_warn(message: Message, bot: Bot, db: Database, config: Config) -> None:
    if not await _require_admin(message, bot, config) or not (user := await _target(message)):
        return
    await _give_warn(message, bot, db, user, reason="решение администратора")


async def _give_warn(message: Message, bot: Bot, db: Database, user: User, reason: str) -> None:
    g = await db.group(message.chat.id)
    count = await db.add_warn(message.chat.id, user.id)
    if count >= g.warn_limit:
        await db.reset_warns(message.chat.id, user.id)
        ok = await _safe(
            bot.restrict_chat_member(
                message.chat.id, user.id, permissions=NO_PERMS, until_date=timedelta(minutes=WARN_MUTE_MIN)
            ),
            message,
        )
        if ok:
            await message.answer(
                f"🔇 {mention(user)} получил {count}/{g.warn_limit} предупреждений и замьючен на {WARN_MUTE_MIN} мин."
            )
    else:
        await message.answer(f"⚠️ {mention(user)}, предупреждение {count}/{g.warn_limit}: {escape(reason)}")


@router.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject, bot: Bot, config: Config) -> None:
    if not await _require_admin(message, bot, config) or not (user := await _target(message)):
        return
    minutes = int(command.args) if command.args and command.args.strip().isdigit() else 60
    minutes = max(1, min(minutes, 60 * 24 * 30))
    if await _safe(
        bot.restrict_chat_member(message.chat.id, user.id, permissions=NO_PERMS, until_date=timedelta(minutes=minutes)),
        message,
    ):
        await message.answer(f"🔇 {mention(user)} замьючен на {minutes} мин.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot, db: Database, config: Config) -> None:
    if not await _require_admin(message, bot, config) or not (user := await _target(message)):
        return
    if await _safe(bot.restrict_chat_member(message.chat.id, user.id, permissions=ALL_PERMS), message):
        await db.reset_warns(message.chat.id, user.id)
        await message.answer(f"🔊 {mention(user)} снова может писать.")


@router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot, config: Config) -> None:
    if not await _require_admin(message, bot, config) or not (user := await _target(message)):
        return
    if await _safe(bot.ban_chat_member(message.chat.id, user.id), message):
        await message.answer(f"⛔ {mention(user)} заблокирован.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database) -> None:
    top = await db.top(message.chat.id)
    if not top:
        await message.answer("📊 Пока нет статистики — пишите больше 🙂")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else f'{i + 1}.'} {escape(s.name or str(s.user_id))} — {s.count}"
        for i, s in enumerate(top)
    ]
    await message.answer("📊 <b>Самые активные</b>\n\n" + "\n".join(lines))


@router.message(Command("giveaway"))
async def cmd_giveaway(message: Message, command: CommandObject, bot: Bot, db: Database, config: Config) -> None:
    if not await _require_admin(message, bot, config):
        return
    args = (command.args or "").strip()
    winners = 1
    if args.split(" ", 1)[0].isdigit():
        first, _, rest = args.partition(" ")
        winners, args = max(1, min(int(first), 50)), rest.strip()
    if not args:
        await message.reply("Пример: <code>/giveaway 2 Telegram Premium на месяц</code>")
        return
    creator = message.from_user.id if message.from_user else 0
    g = await db.create_giveaway(message.chat.id, creator, args, winners)
    await message.answer(
        f"🎁 <b>Розыгрыш!</b>\n\nПриз: <b>{escape(g.prize)}</b>\nПобедителей: {g.winners}\n\n"
        "Жмите кнопку, чтобы участвовать 👇",
        reply_markup=kb.giveaway_inline(g.id, 0),
    )


@router.callback_query(F.data.startswith("gw:join:"))
async def cb_join(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    g = await db.get_giveaway(gid)
    if g is None or g.finished:
        await callback.answer("Розыгрыш уже завершён", show_alert=True)
        return
    new, total = await db.join_giveaway(gid, callback.from_user.id, callback.from_user.full_name)
    if new:
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=kb.giveaway_inline(gid, total))
    await callback.answer("Вы участвуете! 🍀" if new else "Вы уже участвуете 😉")


@router.callback_query(F.data.startswith("gw:draw:"))
async def cb_draw(callback: CallbackQuery, bot: Bot, db: Database, config: Config) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    g = await db.get_giveaway(gid)
    if g is None:
        await callback.answer()
        return
    if callback.from_user.id != g.creator_id and not await is_admin(
        bot, callback.message.chat.id, callback.from_user.id, config
    ):
        await callback.answer("Итоги подводит администратор", show_alert=True)
        return
    if g.finished:
        await callback.answer("Итоги уже подведены", show_alert=True)
        return
    winners = await db.draw_giveaway(gid)
    if not winners:
        text = f"🎁 Розыгрыш «{escape(g.prize)}» завершён — участников не было 😢"
    else:
        names = "\n".join(
            f"🏆 <a href=\"tg://user?id={w.user_id}\">{escape(w.name or str(w.user_id))}</a>" for w in winners
        )
        text = f"🎉 <b>Итоги розыгрыша</b>\n\nПриз: <b>{escape(g.prize)}</b>\n\n{names}\n\nПоздравляем!"
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=None)
    await callback.answer()


# ---------- все остальные сообщения: статистика, антиспам, ИИ ----------
def _has_link(message: Message) -> bool:
    for ent in (message.entities or []) + (message.caption_entities or []):
        if ent.type in {MessageEntityType.URL, MessageEntityType.TEXT_LINK}:
            return True
    return bool(LINK_RE.search(message.text or message.caption or ""))


def _is_flood(chat_id: int, user_id: int) -> bool:
    q = _flood[(chat_id, user_id)]
    now = time.monotonic()
    q.append(now)
    return len(q) == FLOOD_MESSAGES and now - q[0] < FLOOD_WINDOW_SEC


async def _addressed_to_bot(message: Message, bot: Bot) -> str | None:
    me = await bot.me()
    text = message.text or ""
    if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == me.id:
        return text
    tag = f"@{me.username}".lower()
    if me.username and tag in text.lower():
        return re.sub(re.escape(tag), "", text, flags=re.IGNORECASE).strip() or "привет"
    return None


@router.message()
async def on_group_message(message: Message, bot: Bot, db: Database, ai: AIService, config: Config) -> None:
    user = message.from_user
    if user is None or user.is_bot or message.sender_chat:
        return
    asyncio.create_task(db.count_message(message.chat.id, user.id, user.full_name))
    g = await db.group(message.chat.id)

    if (g.antilink or g.antiflood) and not await is_admin(bot, message.chat.id, user.id, config):
        if g.antilink and _has_link(message):
            with suppress(TelegramBadRequest, TelegramForbiddenError):
                await message.delete()
            await _give_warn(message, bot, db, user, reason="ссылки запрещены")
            return
        if g.antiflood and _is_flood(message.chat.id, user.id):
            _flood.pop((message.chat.id, user.id), None)
            if await _safe(
                bot.restrict_chat_member(
                    message.chat.id, user.id, permissions=NO_PERMS, until_date=timedelta(minutes=FLOOD_MUTE_MIN)
                ),
                message,
            ):
                await message.answer(f"🔇 {mention(user)}, не флуди! Мут на {FLOOD_MUTE_MIN} мин.")
            return

    if not g.ai_reply or not message.text or message.text.startswith("/"):
        return
    question = await _addressed_to_bot(message, bot)
    if question is None:
        return
    scope = f"g:{message.chat.id}"
    await db.add_dialog(scope, "user", f"{user.first_name}: {question}", keep=30)
    history = await db.history(scope, 12)
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        answer = await ai.chat(GROUP_PROMPT, history, max_tokens=400)
    except AIError:
        return
    parts = humanize(answer, max_parts=3)
    await db.add_dialog(scope, "model", "\n".join(parts), keep=30)
    first, *rest = parts or [answer]
    await message.reply(first, parse_mode=None)
    if rest:
        await send_like_human(bot, message.chat.id, rest)
