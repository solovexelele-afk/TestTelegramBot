"""Регистрация всех роутеров."""

from aiogram import Router

from bot.handlers import common, errors, fallback, user


def get_root_router() -> Router:
    root = Router(name="root")
    # Порядок важен: fallback — последним.
    root.include_routers(common.router, user.router, errors.router, fallback.router)
    return root
