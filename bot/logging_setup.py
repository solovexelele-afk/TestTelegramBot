"""Настройка логирования: консоль + (опционально) файл с ротацией."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from bot.config import BASE_DIR

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO", to_file: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if to_file:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_dir / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
        )

    logging.basicConfig(level=level, format=LOG_FORMAT, handlers=handlers, force=True)
    # Слишком шумные библиотеки
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
