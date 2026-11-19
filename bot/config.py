"""Загрузка конфигурации из переменных окружения / файла .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env нужен только локально; на хостинге переменные задаются в панели.
load_dotenv(BASE_DIR / ".env")


class ConfigError(RuntimeError):
    """Ошибка конфигурации (например, не задан токен)."""


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    mode: str  # "polling" | "webhook"
    log_level: str
    log_to_file: bool
    # webhook
    webhook_base_url: str
    webhook_path: str
    webhook_secret: str
    host: str
    port: int


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        raise ConfigError(
            "Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен от @BotFather."
        )

    # Render автоматически выставляет RENDER_EXTERNAL_URL — используем его по умолчанию.
    base_url = (os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    mode = os.getenv("BOT_MODE", "").strip().lower() or ("webhook" if base_url else "polling")
    if mode not in {"polling", "webhook"}:
        raise ConfigError("BOT_MODE должен быть 'polling' или 'webhook'.")

    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if mode == "webhook":
        if not base_url:
            raise ConfigError("Для режима webhook нужен WEBHOOK_BASE_URL (или RENDER_EXTERNAL_URL).")
        if not secret:
            raise ConfigError("Для режима webhook задайте WEBHOOK_SECRET.")

    return Config(
        bot_token=token,
        mode=mode,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_to_file=_get_bool("LOG_TO_FILE", default=mode == "polling"),
        webhook_base_url=base_url,
        webhook_path=os.getenv("WEBHOOK_PATH", "/webhook"),
        webhook_secret=secret,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
    )
