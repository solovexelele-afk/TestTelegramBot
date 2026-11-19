"""Загрузка конфигурации из переменных окружения / файла .env."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env нужен только локально; на хостинге переменные задаются в панели.
load_dotenv(BASE_DIR / ".env")


class ConfigError(RuntimeError):
    """Ошибка конфигурации (например, не задан токен)."""


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_ids(name: str) -> frozenset[int]:
    raw = os.getenv(name, "")
    return frozenset(int(x) for x in raw.replace(";", ",").split(",") if x.strip().lstrip("-").isdigit())


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'bot.db').as_posix()}"
    # Neon/Render/Supabase выдают postgres:// или postgresql:// — переводим на async-драйвер.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    # asyncpg не понимает sslmode/channel_binding из строки подключения Neon.
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        url = url.split("?", 1)[0]
    return url


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
    keep_alive: bool
    # данные
    database_url: str
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    # ИИ
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    history_limit: int = 20


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

    raw_secret = os.getenv("WEBHOOK_SECRET", "").strip()
    # Telegram допускает в secret_token только A-Z a-z 0-9 _ - (1..256 символов),
    # а Render генерирует base64. Приводим к hex SHA-256 — стабильно и всегда валидно.
    secret = hashlib.sha256(raw_secret.encode()).hexdigest() if raw_secret else ""
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
        keep_alive=_get_bool("KEEP_ALIVE", default=False),
        database_url=_database_url(),
        admin_ids=_get_ids("ADMIN_IDS"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "").strip() or "gemini-flash-latest",
        history_limit=int(os.getenv("AI_HISTORY_LIMIT", "20")),
    )
