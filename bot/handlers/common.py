"""/start, /help, навигация по меню, /id, /profile, /persona."""

from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.db import Database
from bot.services.ai import AIService
from bot.services.personas import PERSONAS

router = Router(name="common")
router.message.filter(F.chat.type == ChatType.PRIVATE)


async def _edit(callback: CallbackQuery, text: str, markup=None) -> None:
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    await db.touch_user(message.from_user.id)
    await message.answer("Главное меню открыто ⬇️", reply_markup=kb.main_menu())
    await message.answer(texts.start_text(message.from_user), reply_markup=kb.start_inline())


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP_TEXT, reply_markup=kb.back_inline())


@router.message(Command("id"))
@router.message(F.text == kb.BTN_ID)
async def cmd_id(message: Message) -> None:
    await message.answer(texts.id_text(message.from_user, message.chat))


@router.message(Command("profile"))
@router.message(F.text == kb.BTN_PROFILE)
async def cmd_profile(message: Message, db: Database, ai: AIService) -> None:
    user = await db.touch_user(message.from_user.id)
    await message.answer(
        texts.profile_text(message.from_user, user.first_seen, user.persona, ai.provider),
        reply_markup=kb.profile_inline(),
    )


@router.message(Command("persona"))
async def cmd_persona(message: Message, db: Database) -> None:
    user = await db.touch_user(message.from_user.id)
    await message.answer("🎭 Выберите характер собеседника:", reply_markup=kb.persona_inline(user.persona))


@router.message(F.text == kb.BTN_CHAT)
async def btn_chat(message: Message) -> None:
    await message.answer("💬 Я тут! Пиши что угодно — поболтаем 🙂")


# ---------- inline-меню ----------
@router.callback_query(F.data == "menu:start")
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(callback, texts.start_text(callback.from_user), kb.start_inline())


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    await _edit(callback, texts.HELP_TEXT, kb.back_inline())


@router.callback_query(F.data == "menu:groups")
async def cb_groups(callback: CallbackQuery) -> None:
    await _edit(callback, texts.GROUPS_TEXT, kb.back_inline())


@router.callback_query(F.data == "menu:chat")
async def cb_chat(callback: CallbackQuery) -> None:
    await callback.message.answer("💬 Я тут! Пиши что угодно — поболтаем 🙂")
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, db: Database, ai: AIService) -> None:
    user = await db.touch_user(callback.from_user.id)
    await _edit(
        callback,
        texts.profile_text(callback.from_user, user.first_seen, user.persona, ai.provider),
        kb.profile_inline(),
    )


@router.callback_query(F.data == "menu:persona")
async def cb_persona_menu(callback: CallbackQuery, db: Database) -> None:
    user = await db.touch_user(callback.from_user.id)
    await _edit(callback, "🎭 Выберите характер собеседника:", kb.persona_inline(user.persona))


@router.callback_query(F.data.startswith("persona:"))
async def cb_persona(callback: CallbackQuery, db: Database) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in PERSONAS:
        await callback.answer()
        return
    if key == "me" and await db.count_style(callback.from_user.id) == 0:
        await callback.answer(
            "Я ещё не знаю твой стиль. Пришли мне экспорт переписки (result.json) — подробности в /business → 🧬 Мой стиль",
            show_alert=True,
        )
        return
    await db.set_persona(callback.from_user.id, key)
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=kb.persona_inline(key))
    await callback.answer(f"Теперь я: {PERSONAS[key][0]}")


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(callback, "Отменено ✖️")
