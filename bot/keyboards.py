"""Клавиатуры бота."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BTN_PROFILE = "👤 Профиль"
BTN_ID = "🆔 Мой ID"
BTN_HELP = "❓ Помощь"


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_PROFILE)
    kb.button(text=BTN_ID)
    kb.button(text=BTN_HELP)
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие…")


def start_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Мой профиль", callback_data="menu:profile")
    kb.button(text="🆔 Узнать ID", callback_data="menu:id")
    kb.button(text="❓ Что умеет бот", callback_data="menu:help")
    kb.adjust(2, 1)
    return kb.as_markup()


def profile_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="menu:profile")
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    kb.adjust(2)
    return kb.as_markup()


def back_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    return kb.as_markup()
