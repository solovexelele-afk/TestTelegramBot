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
from contextlib import suppress

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from bot import __version__
from bot.config import BASE_DIR, Config, ConfigError, load_config
from bot.db import Database
from bot.handlers import get_root_router
from bot.logging_setup import setup_logging
from bot.middlewares import LoggingMiddleware
from bot.services.ai import AIService

logger = logging.getLogger("bot")
PID_FILE = BASE_DIR / "bot.pid"

PRIVATE_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="img", description="Сгенерировать картинку"),
    BotCommand(command="persona", description="Характер ИИ"),
    BotCommand(command="reset", description="Забыть диалог"),
    BotCommand(command="business", description="Автоответчик"),
    BotCommand(command="profile", description="Мой профиль"),
    BotCommand(command="id", description="Мой Telegram ID"),
    BotCommand(command="help", description="Все команды"),
]
GROUP_COMMANDS = [
    BotCommand(command="settings", description="Настройки бота в чате"),
    BotCommand(command="stats", description="Топ активных"),
    BotCommand(command="giveaway", description="Розыгрыш: [кол-во] приз"),
    BotCommand(command="img", description="Сгенерировать картинку"),
    BotCommand(command="warn", description="Предупреждение (ответом)"),
    BotCommand(command="mute", description="Мут [мин] (ответом)"),
    BotCommand(command="unmute", description="Снять мут (ответом)"),
    BotCommand(command="ban", description="Бан (ответом)"),
]


def build_dispatcher(config: Config | None = None) -> Dispatcher:
    dp = Dispatcher()
    for observer in (dp.message, dp.callback_query, dp.business_message):
        observer.outer_middleware(LoggingMiddleware())
    dp.include_router(get_root_router())
    if config is not None:
        db = Database(config.database_url)
        ai = AIService(config.gemini_api_key, config.gemini_model)
        dp["config"], dp["db"], dp["ai"] = config, db, ai

        async def init_resources() -> None:
            await db.init()
            logger.info("База данных: %s", config.database_url.split("://", 1)[0])
            logger.info("ИИ: %s", ai.provider)

        async def close_resources() -> None:
            await ai.close()
            await db.close()

        dp.startup.register(init_resources)
        dp.shutdown.register(close_resources)
    return dp


async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    logger.info("Бот запущен: @%s (id=%s), версия %s", me.username, me.id, __version__)


async def run_polling(config: Config) -> None:
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(config)
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


async def keep_alive(url: str, interval: int = 600) -> None:
    """Пингует собственный /health, чтобы бесплатный инстанс Render не засыпал."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        while True:
            await asyncio.sleep(interval)
            with suppress(Exception):
                async with session.get(url) as resp:
                    logger.debug("keep-alive %s -> %s", url, resp.status)


def run_webhook(config: Config) -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(config)
    webhook_url = f"{config.webhook_base_url}{config.webhook_path}"
    background: list[asyncio.Task] = []

    async def startup_webhook(bot: Bot) -> None:
        await on_startup(bot)
        await bot.set_webhook(
            webhook_url,
            secret_token=config.webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info("Режим: webhook, URL: %s", webhook_url)
        if config.keep_alive:
            background.append(asyncio.create_task(keep_alive(f"{config.webhook_base_url}/health")))
            logger.info("Keep-alive включён (пинг каждые 10 мин)")

    async def shutdown_webhook(bot: Bot) -> None:
        for task in background:
            task.cancel()
        await bot.session.close()

    dp.startup.register(startup_webhook)
    dp.shutdown.register(shutdown_webhook)

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
