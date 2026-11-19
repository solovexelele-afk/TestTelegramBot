"""Генерация картинок через Pollinations.

* Без ключа (по умолчанию): image.pollinations.ai — бесплатно, но 1 картинка в 45 секунд с одного IP
  и водяной знак «pollinations.ai» внизу справа. Знак убираем: запрашиваем картинку немного выше
  нужной и отрезаем нижнюю полосу. Очередь соблюдает лимит и ждёт столько, сколько просит сервис.
* С ключом POLLINATIONS_API_KEY (бесплатно на enter.pollinations.ai): gen.pollinations.ai —
  без жёсткого лимита и без водяного знака.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import random
import re
import time
from urllib.parse import quote

import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)

FREE_URL = "https://image.pollinations.ai/prompt/{prompt}"
KEY_URL = "https://gen.pollinations.ai/image/{prompt}"
FREE_INTERVAL_SEC = 46  # «1 image every 45 seconds per IP»
CROP_EXTRA = 0.09  # водяной знак занимает ~6% высоты снизу — отрезаем с запасом
MAX_WAIT_SEC = 180
RETRY_RE = re.compile(r"retry after (\d+)\s*s", re.IGNORECASE)

_lock = asyncio.Lock()
_next_free_slot = 0.0  # time.monotonic(), когда можно делать следующий бесплатный запрос
_queue = 0


class ImageError(RuntimeError):
    pass


_VERTICAL_RE = re.compile(
    r"\b(вертикальн\w*|на телефон|обои на телефон|для телефона|сторис|stories|портретн\w*|9[:x×]16)\b", re.IGNORECASE
)
_HORIZONTAL_RE = re.compile(
    r"\b(горизонтальн\w*|широк\w*|на (пк|комп\w*|рабочий стол)|для (пк|компа)|16[:x×]9|баннер\w*|обложк\w*)\b",
    re.IGNORECASE,
)


def detect_format(prompt: str) -> tuple[int, int, str]:
    """Определяет формат по словам в запросе. Возвращает (ширина, высота, название)."""
    if _VERTICAL_RE.search(prompt):
        return 768, 1344, "вертикальная 9:16"
    if _HORIZONTAL_RE.search(prompt):
        return 1344, 768, "горизонтальная 16:9"
    return 1024, 1024, "квадрат"


def _api_key() -> str:
    return os.getenv("POLLINATIONS_API_KEY", "").strip()


def estimated_wait() -> int:
    """Примерное ожидание в секундах для нового запроса (для сообщения пользователю)."""
    if _api_key():
        return 0
    now = time.monotonic()
    return max(0, int(_next_free_slot - now)) + _queue * FREE_INTERVAL_SEC


def _crop_watermark(data: bytes, width: int, height: int) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        w, h = img.size
        target_h = min(h, round(w * height / width), round(h / (1 + CROP_EXTRA)))
        out = io.BytesIO()
        img.crop((0, 0, w, target_h)).save(out, format="JPEG", quality=93)
        return out.getvalue()


async def _fetch(session: aiohttp.ClientSession, url: str, params: dict, headers: dict) -> tuple[int, str, bytes]:
    async with session.get(url, params=params, headers=headers) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), await resp.read()


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> bytes:
    global _next_free_slot, _queue
    key = _api_key()
    url = (KEY_URL if key else FREE_URL).format(prompt=quote(prompt, safe=""))
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    params = {
        "width": str(width),
        "height": str(height if key else round(height * (1 + CROP_EXTRA))),
        "nologo": "true",
        "private": "true",
        "seed": str(random.randint(1, 2_000_000_000)),
    }
    timeout = aiohttp.ClientTimeout(total=120)

    _queue += 1
    acquired = False
    try:
        async with _lock, aiohttp.ClientSession(timeout=timeout) as session:
            _queue -= 1
            acquired = True
            deadline = time.monotonic() + MAX_WAIT_SEC
            while time.monotonic() < deadline:
                if not key:
                    await asyncio.sleep(max(0.0, _next_free_slot - time.monotonic()))
                try:
                    status, ctype, body = await _fetch(session, url, params, headers)
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                    logger.warning("Pollinations image: %s", exc)
                    await asyncio.sleep(5)
                    continue

                if status == 200 and ctype.startswith("image/") and len(body) > 1000:
                    if not key:
                        _next_free_slot = time.monotonic() + FREE_INTERVAL_SEC
                        return await asyncio.to_thread(_crop_watermark, body, width, height)
                    return body

                text = body[:300].decode("utf-8", "replace")
                logger.warning("Pollinations image: HTTP %s %s", status, text[:160])
                if status in (401, 403) and key:
                    raise ImageError("Неверный POLLINATIONS_API_KEY")
                match = RETRY_RE.search(text)
                wait = int(match.group(1)) + 1 if match else (FREE_INTERVAL_SEC if status == 402 else 8)
                if not key:
                    _next_free_slot = time.monotonic() + wait
                else:
                    await asyncio.sleep(wait)
                params["seed"] = str(random.randint(1, 2_000_000_000))
    finally:
        if not acquired:
            _queue -= 1
    raise ImageError("Не удалось сгенерировать картинку")
