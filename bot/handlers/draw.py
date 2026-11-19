"""Генерация картинок: /img, кнопка «Картинка», «Ещё вариант»."""

from __future__ import annotations

import logging
from contextlib import suppress
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from bot import keyboards as kb
from bot import texts
from bot.services.ai import AIService
from bot.services.images import ImageError, estimated_wait, generate_image

router = Router(name="draw")
logger = logging.getLogger(__name__)

# последний промпт пользователя — для кнопки «Ещё вариант»
_last_prompt: dict[int, str] = {}


class DrawState(StatesGroup):
    waiting_prompt = State()


async def _draw(bot: Bot, chat_id: int, user_id: int, prompt: str, ai: AIService, reply_to: int | None = None) -> None:
    wait = estimated_wait()
    note = texts.IMAGE_WAIT if wait < 10 else f"🎨 Поставил в очередь, рисую через ~{wait} сек (бесплатный лимит)…"
    status = await bot.send_message(chat_id, note, reply_to_message_id=reply_to)
    try:
        async with ChatActionSender.upload_photo(bot=bot, chat_id=chat_id):
            en_prompt = await ai.to_image_prompt(prompt)
            data = await generate_image(en_prompt)
        _last_prompt[user_id] = prompt
        await bot.send_photo(
            chat_id,
            BufferedInputFile(data, filename="image.jpg"),
            caption=f"🎨 {escape(prompt[:900])}",
            reply_markup=kb.image_again_inline(),
            reply_to_message_id=reply_to,
        )
    except ImageError:
        await bot.send_message(chat_id, texts.IMAGE_FAIL)
    finally:
        with suppress(TelegramBadRequest):
            await status.delete()


@router.message(Command("img", "image", "draw"))
async def cmd_img(message: Message, command: CommandObject, bot: Bot, ai: AIService, state: FSMContext) -> None:
    if not command.args:
        if message.chat.type == "private":
            await state.set_state(DrawState.waiting_prompt)
            await message.answer(texts.IMAGE_ASK, reply_markup=kb.cancel_inline())
        else:
            await message.reply("Напишите так: <code>/img кот в очках</code>")
        return
    await _draw(bot, message.chat.id, message.from_user.id, command.args, ai, reply_to=message.message_id)


@router.message(F.text == kb.BTN_IMAGE)
async def btn_image(message: Message, state: FSMContext) -> None:
    await state.set_state(DrawState.waiting_prompt)
    await message.answer(texts.IMAGE_ASK, reply_markup=kb.cancel_inline())


@router.callback_query(F.data == "menu:image")
async def cb_image(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DrawState.waiting_prompt)
    await callback.message.answer(texts.IMAGE_ASK, reply_markup=kb.cancel_inline())
    await callback.answer()


@router.message(DrawState.waiting_prompt, F.text)
async def got_prompt(message: Message, bot: Bot, ai: AIService, state: FSMContext) -> None:
    if message.text.startswith("/") or message.text in kb.MENU_BUTTONS:
        await state.clear()
        await message.answer("Рисование отменено. Нажмите кнопку ещё раз 🙂")
        return
    await state.clear()
    await _draw(bot, message.chat.id, message.from_user.id, message.text, ai)


@router.callback_query(F.data == "img:again")
async def cb_again(callback: CallbackQuery, bot: Bot, ai: AIService) -> None:
    prompt = _last_prompt.get(callback.from_user.id)
    if not prompt and callback.message.caption:
        prompt = callback.message.caption.removeprefix("🎨 ").strip()
    if not prompt:
        await callback.answer("Не помню описание — отправьте его заново", show_alert=True)
        return
    await callback.answer("Рисую ещё вариант…")
    await _draw(bot, callback.message.chat.id, callback.from_user.id, prompt, ai)
