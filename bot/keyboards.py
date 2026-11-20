"""Клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.services.personas import PERSONAS

BTN_CHAT = "💬 Поболтать"
BTN_IMAGE = "🎨 Картинка"
BTN_PROFILE = "👤 Профиль"
BTN_ID = "🆔 Мой ID"
BTN_BUSINESS = "💼 Автоответчик"
BTN_HELP = "❓ Помощь"

MENU_BUTTONS = {BTN_CHAT, BTN_IMAGE, BTN_PROFILE, BTN_ID, BTN_BUSINESS, BTN_HELP}


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for text in (BTN_CHAT, BTN_IMAGE, BTN_PROFILE, BTN_ID, BTN_BUSINESS, BTN_HELP):
        kb.button(text=text)
    kb.adjust(2, 2, 2)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Напиши мне что-нибудь…")


def start_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Поболтать", callback_data="menu:chat")
    kb.button(text="🎨 Нарисовать", callback_data="menu:image")
    kb.button(text="👥 Для групп", callback_data="menu:groups")
    kb.button(text="💼 Автоответчик", callback_data="menu:business")
    kb.button(text="👤 Профиль", callback_data="menu:profile")
    kb.button(text="❓ Помощь", callback_data="menu:help")
    kb.adjust(2, 2, 2)
    return kb.as_markup()


def back_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    return kb.as_markup()


def profile_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎭 Характер ИИ", callback_data="menu:persona")
    kb.button(text="🧹 Забыть диалог", callback_data="ai:reset")
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    kb.adjust(2, 1)
    return kb.as_markup()


def persona_inline(current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, (title, _) in PERSONAS.items():
        kb.button(text=("✅ " if key == current else "") + title, callback_data=f"persona:{key}")
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def image_again_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Ещё вариант", callback_data="img:again")
    kb.button(text="🎨 Новая картинка", callback_data="menu:image")
    kb.adjust(2)
    return kb.as_markup()


def cancel_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="cancel")
    return kb.as_markup()


def group_settings_inline(g) -> InlineKeyboardMarkup:  # g: GroupSettings
    def mark(v: bool) -> str:
        return "✅" if v else "❌"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"{mark(g.welcome)} Приветствие", callback_data="gs:welcome")
    kb.button(text=f"{mark(g.antilink)} Антиссылки", callback_data="gs:antilink")
    kb.button(text=f"{mark(g.antiflood)} Антифлуд", callback_data="gs:antiflood")
    kb.button(text=f"{mark(g.ai_reply)} ИИ-ответы", callback_data="gs:ai_reply")
    kb.adjust(2, 2)
    return kb.as_markup()


def giveaway_inline(gid: int, count: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🎉 Участвовать ({count})", callback_data=f"gw:join:{gid}")
    kb.button(text="🏁 Подвести итоги", callback_data=f"gw:draw:{gid}")
    kb.adjust(1)
    return kb.as_markup()


def business_inline(mode: str, pause: int) -> InlineKeyboardMarkup:
    def mark(m: str) -> str:
        return "✅ " if mode == m else ""

    kb = InlineKeyboardBuilder()
    kb.button(text=f"{mark('ai')}🤖 ИИ-ответы", callback_data="biz:mode:ai")
    kb.button(text=f"{mark('away')}📝 Шаблон", callback_data="biz:mode:away")
    kb.button(text=f"{mark('off')}⏸ Выключить", callback_data="biz:mode:off")
    kb.button(text="🧬 Мой стиль", callback_data="biz:style")
    kb.button(text="✏️ Текст шаблона", callback_data="biz:away_text")
    kb.button(text="🧾 О себе для ИИ", callback_data="biz:instructions")
    kb.button(text=f"⏱ Пауза после вас: {pause} мин", callback_data="biz:pause")
    kb.adjust(3, 1, 2, 1)
    return kb.as_markup()


def style_only_inline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧬 Мой стиль", callback_data="biz:style")
    kb.button(text="⬅️ В меню", callback_data="menu:start")
    kb.adjust(1)
    return kb.as_markup()


def style_inline(has_samples: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_samples:
        kb.button(text="🗑 Забыть мой стиль", callback_data="biz:style_reset")
    kb.button(text="⬅️ Назад", callback_data="menu:business")
    kb.adjust(1)
    return kb.as_markup()
