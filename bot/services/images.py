"""Генерация картинок через бесплатный image.pollinations.ai (без ключа)."""

from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

IMAGE_URL = "https://image.pollinations.ai/prompt/{prompt}"


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
        for attempt in range(2):
            try:
                async with session.get(url, params=params) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    if resp.status == 200 and ctype.startswith("image/"):
                        data = await resp.read()
                        if len(data) > 1000:
                            return data
                    logger.warning("Pollinations image: HTTP %s, %s", resp.status, ctype)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("Pollinations image, попытка %s: %s", attempt + 1, exc)
            await asyncio.sleep(2)
    raise ImageError("Не удалось сгенерировать картинку")
