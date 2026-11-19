"""/start и /help."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import texts
from bot.storage import registry

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    registry.touch(message.from_user.id)
    await message.answer("Главное меню открыто ⬇️", reply_markup=kb.main_menu())
    await message.answer(texts.start_text(message.from_user), reply_markup=kb.start_inline())


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP_TEXT, reply_markup=kb.back_inline())


@router.callback_query(F.data == "menu:start")
async def cb_start(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        texts.start_text(callback.from_user), reply_markup=kb.start_inline()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(texts.HELP_TEXT, reply_markup=kb.back_inline())
    await callback.answer()
