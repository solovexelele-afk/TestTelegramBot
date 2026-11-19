"""Точка входа: python -m bot

Режимы:
  * polling — локальный запуск на ПК (по умолчанию);
  * webhook — облачный хостинг (Render и т.п.), включается автоматически,
    если задан WEBHOOK_BASE_URL или RENDER_EXTERNAL_URL.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot import __version__
from bot.config import BASE_DIR, Config, ConfigError, load_config
from bot.handlers import get_root_router
from bot.logging_setup import setup_logging
from bot.middlewares import LoggingMiddleware

logger = logging.getLogger("bot")
PID_FILE = BASE_DIR / "bot.pid"

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="help", description="Список команд"),
    BotCommand(command="id", description="Мой Telegram ID"),
    BotCommand(command="profile", description="Мой профиль"),
]


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(LoggingMiddleware())
    dp.include_router(get_root_router())
    return dp


async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    await bot.set_my_commands(COMMANDS)
    logger.info("Бот запущен: @%s (id=%s), версия %s", me.username, me.id, __version__)


async def run_polling(config: Config) -> None:
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    dp.startup.register(on_startup)

    # Снимаем webhook, иначе getUpdates вернёт конфликт.
    await bot.delete_webhook(drop_pending_updates=False)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    try:
        logger.info("Режим: polling")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        PID_FILE.unlink(missing_ok=True)
        await bot.session.close()


def run_webhook(config: Config) -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    webhook_url = f"{config.webhook_base_url}{config.webhook_path}"

    async def startup_webhook(bot: Bot) -> None:
        await on_startup(bot)
        await bot.set_webhook(
            webhook_url,
            secret_token=config.webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info("Режим: webhook, URL: %s", webhook_url)

    dp.startup.register(startup_webhook)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "version": __version__})

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=config.webhook_secret).register(
        app, path=config.webhook_path
    )
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=config.host, port=config.port, print=None)


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        setup_logging()
        logger.error("%s", exc)
        return 1

    setup_logging(config.log_level, config.log_to_file)
    try:
        if config.mode == "webhook":
            run_webhook(config)
        else:
            asyncio.run(run_polling(config))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception:
        logger.exception("Критическая ошибка, бот остановлен")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
