"""Тексты сообщений (HTML-разметка)."""

from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.types import Chat, User


def start_text(user: User) -> str:
    return (
        f"👋 Привет, <b>{escape(user.first_name)}</b>!\n\n"
        "Я — <b>TestTelegramBot</b>, тестовый бот на <i>aiogram 3</i>.\n"
        "Выберите действие кнопками ниже или воспользуйтесь командами.\n\n"
        "📋 /help — список команд"
    )


HELP_TEXT = (
    "📖 <b>Доступные команды</b>\n\n"
    "/start — приветствие и главное меню\n"
    "/help — эта справка\n"
    "/id — ваш Telegram ID и ID чата\n"
    "/profile — информация о вашем профиле\n\n"
    "💡 Также можно пользоваться кнопками внизу экрана."
)


def id_text(user: User, chat: Chat) -> str:
    return (
        "🆔 <b>Идентификаторы</b>\n\n"
        f"Ваш ID: <code>{user.id}</code>\n"
        f"ID чата: <code>{chat.id}</code>\n"
        f"Тип чата: <i>{escape(chat.type)}</i>\n\n"
        "<i>Нажмите на число, чтобы скопировать.</i>"
    )


def profile_text(user: User, first_seen: datetime | None) -> str:
    username = f"@{escape(user.username)}" if user.username else "—"
    full_name = escape(user.full_name)
    lang = escape(user.language_code or "—")
    premium = "✅ да" if user.is_premium else "❌ нет"
    seen = first_seen.strftime("%d.%m.%Y %H:%M UTC") if first_seen else "—"
    return (
        "👤 <b>Ваш профиль</b>\n\n"
        f"<b>Имя:</b> {full_name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Язык:</b> {lang}\n"
        f"<b>Telegram Premium:</b> {premium}\n"
        f"<b>Первый запуск бота:</b> {seen}"
    )


ERROR_TEXT = "⚠️ Произошла ошибка. Попробуйте ещё раз чуть позже."
UNKNOWN_TEXT = "🤔 Я не знаю такой команды. Нажмите /help, чтобы увидеть список."
