"""Регистрация всех роутеров."""

from aiogram import Router

from bot.handlers import ai_chat, business, common, draw, errors, group


def get_root_router() -> Router:
    root = Router(name="root")
    # Ошибки «всплывают» к родителю — глобальный обработчик вешаем на корневой роутер.
    root.error.register(errors.on_error)
    # Порядок важен: ai_chat перехватывает весь текст в личке — поэтому последним.
    root.include_routers(
        common.router,
        draw.router,
        business.router,
        group.router,
        ai_chat.router,
    )
    return root
