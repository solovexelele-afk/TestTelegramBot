"""Ответ на всё, что не распознано другими хендлерами."""

from aiogram import Router
from aiogram.types import Message

from bot import texts

router = Router(name="fallback")


@router.message()
async def unknown(message: Message) -> None:
    await message.answer(texts.UNKNOWN_TEXT)
