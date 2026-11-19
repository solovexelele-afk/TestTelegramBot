"""Генерация картинок через бесплатный image.pollinations.ai (без ключа)."""

from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

IMAGE_URL = "https://image.pollinations.ai/prompt/{prompt}"
# анонимный доступ — один запрос за раз, иначе сервис отвечает 402/429
_lock = asyncio.Lock()


class ImageError(RuntimeError):
    pass


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> bytes:
    params = {
        "width": str(width),
        "height": str(height),
        "nologo": "true",
        "private": "true",
        "seed": str(random.randint(1, 2_000_000_000)),
    }
    url = IMAGE_URL.format(prompt=quote(prompt, safe=""))
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Бесплатный сервис иногда отвечает 402/429/503 под нагрузкой — повторяем с паузой.
        for attempt, delay in enumerate((4, 8, 12), start=1):
            try:
                async with _lock, session.get(url, params=params) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    if resp.status == 200 and ctype.startswith("image/"):
                        data = await resp.read()
                        if len(data) > 1000:
                            return data
                    logger.warning("Pollinations image, попытка %s: HTTP %s, %s", attempt, resp.status, ctype)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("Pollinations image, попытка %s: %s", attempt, exc)
            params["seed"] = str(random.randint(1, 2_000_000_000))
            await asyncio.sleep(delay)
    raise ImageError("Не удалось сгенерировать картинку")
