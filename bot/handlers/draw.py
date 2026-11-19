"""Генерация картинок: /img, кнопка «Картинка», «нарисуй …» в чате, «Ещё вариант»."""

from __future__ import annotations

import logging
import re
import time
from contextlib import suppress
from html import escape

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from bot import keyboards as kb
from bot import texts
from bot.services.ai import AIService
from bot.services.images import ImageError, detect_format, estimated_wait, generate_image
from bot.services.messaging import bump

router = Router(name="draw")
logger = logging.getLogger(__name__)

STATE_TTL_SEC = 180  # ждём описание картинки не дольше 3 минут

# последний промпт пользователя — для кнопки «Ещё вариант»
_last_prompt: dict[int, str] = {}

# «нарисуй кота», «сгенерируй мне аватарку…», «сделай картинку с …»
_DRAW_VERB = r"(нарисуй|нарисовать|нарисуешь|сгенерируй|сгенери|сгенерить|сгенерировать|намалюй|draw)"
_MAKE_VERB = r"(сделай|создай|скинь|покажи|замути|сделаешь)"
# общие слова («картинку», «фото») из описания убираем, смысловые («аватарку», «обои») — оставляем
_GENERIC_NOUN = r"(?:картинк\w*|фот\w*|арт\w*|изображени\w*|рисун\w*|пикч\w*)"
_SPECIFIC_NOUN = r"(?:аватарк\w*|аву|ав[ыу]шк\w*|обо[иея]\w*|мем\w*|стикер\w*)"
_INTENT_RE = re.compile(
    rf"^\s*(?:(?:бро|слушай|плиз|пж|пожалуйста|а)\s*,?\s*)*"
    rf"(?:{_DRAW_VERB}\s*(?:мне\s+)?(?:{_GENERIC_NOUN}\s*)?"
    rf"|{_MAKE_VERB}\s+(?:мне\s+)?(?:{_GENERIC_NOUN}\s*|(?={_SPECIFIC_NOUN})))"
    rf"(?P<prompt>.*)$",
    re.IGNORECASE | re.DOTALL,
)


def image_intent(text: str) -> str | None:
    """Если сообщение — просьба нарисовать, возвращает описание картинки."""
    m = _INTENT_RE.match(text or "")
    if not m:
        return None
    prompt = m.group("prompt").strip(" :,-—")
    return prompt or None


class DrawState(StatesGroup):
    waiting_prompt = State()


async def draw(bot: Bot, chat_id: int, user_id: int, prompt: str, ai: AIService, reply_to: int | None = None) -> None:
    bump(chat_id)  # обрываем недосланный ответ ИИ, если он ещё «печатается»
    width, height, fmt = detect_format(prompt)
    wait = estimated_wait()
    note = f"🎨 рисую ({fmt})…" if wait < 10 else f"🎨 поставил в очередь, нарисую через ~{wait} сек (бесплатный лимит)"
    status = await bot.send_message(chat_id, note, reply_to_message_id=reply_to)
    try:
        async with ChatActionSender.upload_photo(bot=bot, chat_id=chat_id):
            en_prompt = await ai.to_image_prompt(prompt)
            data = await generate_image(en_prompt, width, height)
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


async def _ask_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(DrawState.waiting_prompt)
    await state.update_data(since=time.time())
    await message.answer(texts.IMAGE_ASK, reply_markup=kb.cancel_inline())


@router.message(Command("img", "image", "draw"))
async def cmd_img(message: Message, command: CommandObject, bot: Bot, ai: AIService, state: FSMContext) -> None:
    await state.clear()
    if not command.args:
        if message.chat.type == "private":
            await _ask_prompt(message, state)
        else:
            await message.reply("Напишите так: <code>/img кот в очках</code>")
        return
    await draw(bot, message.chat.id, message.from_user.id, command.args, ai, reply_to=message.message_id)


@router.message(F.text == kb.BTN_IMAGE)
async def btn_image(message: Message, state: FSMContext) -> None:
    await _ask_prompt(message, state)


@router.callback_query(F.data == "menu:image")
async def cb_image(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_prompt(callback.message, state)
    await callback.answer()


@router.message(DrawState.waiting_prompt, F.text, ~F.text.startswith("/"))
async def got_prompt(message: Message, bot: Bot, ai: AIService, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    if time.time() - float(data.get("since", 0)) > STATE_TTL_SEC or message.text in kb.MENU_BUTTONS:
        raise SkipHandler  # давно нажимали «Картинка» — это уже обычное сообщение
    await draw(bot, message.chat.id, message.from_user.id, message.text, ai)


@router.callback_query(F.data == "img:again")
async def cb_again(callback: CallbackQuery, bot: Bot, ai: AIService) -> None:
    prompt = _last_prompt.get(callback.from_user.id)
    if not prompt and callback.message.caption:
        prompt = callback.message.caption.removeprefix("🎨 ").strip()
    if not prompt:
        await callback.answer("Не помню описание — отправьте его заново", show_alert=True)
        return
    await callback.answer("Рисую ещё вариант…")
    await draw(bot, callback.message.chat.id, callback.from_user.id, prompt, ai)
