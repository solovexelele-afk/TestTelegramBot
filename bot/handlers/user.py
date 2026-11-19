"""/id и /profile."""

from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.storage import registry

router = Router(name="user")


@router.message(Command("id"))
@router.message(F.text == kb.BTN_ID)
async def cmd_id(message: Message) -> None:
    await message.answer(texts.id_text(message.from_user, message.chat))


@router.message(Command("profile"))
@router.message(F.text == kb.BTN_PROFILE)
async def cmd_profile(message: Message) -> None:
    registry.touch(message.from_user.id)
    await message.answer(
        texts.profile_text(message.from_user, registry.first_seen(message.from_user.id)),
        reply_markup=kb.profile_inline(),
    )


@router.callback_query(F.data == "menu:id")
async def cb_id(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        texts.id_text(callback.from_user, callback.message.chat), reply_markup=kb.back_inline()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery) -> None:
    registry.touch(callback.from_user.id)
    # "message is not modified" при повторном нажатии «Обновить» — не ошибка.
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            texts.profile_text(callback.from_user, registry.first_seen(callback.from_user.id)),
            reply_markup=kb.profile_inline(),
        )
    await callback.answer("Профиль обновлён")
