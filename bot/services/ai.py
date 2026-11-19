"""ИИ-собеседник.

Основной провайдер — Google Gemini (бесплатный лимит, нужен GEMINI_API_KEY).
Запасной — бесплатный text.pollinations.ai без ключа (если ключа нет или Gemini недоступен).
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/openai"


class AIError(RuntimeError):
    pass


class AIService:
    def __init__(self, gemini_api_key: str, gemini_models: str) -> None:
        self.models = [m.strip() for m in gemini_models.split(",") if m.strip()]
        self._gemini = genai.Client(api_key=gemini_api_key) if gemini_api_key and self.models else None
        self._http: aiohttp.ClientSession | None = None
        self._working: str | None = None  # последняя модель, которая ответила
        self._no_thinking: set[str] = set()  # модели, не принимающие thinking_level

    @property
    def provider(self) -> str:
        if not self._gemini:
            return "Pollinations (без ключа)"
        return f"Gemini ({self._working or self.models[0]})"

    async def _session(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()

    @property
    def can_see(self) -> bool:
        """Понимает ли ИИ фото и голосовые (только Gemini)."""
        return self._gemini is not None

    async def chat(
        self,
        system: str,
        history: list[tuple[str, str]],
        max_tokens: int = 1024,
        media: tuple[bytes, str] | None = None,
    ) -> str:
        """history: [(role, text)], role = 'user' | 'model'. Последний элемент — новое сообщение.

        media — (байты, mime-тип) фото или голосового, прикладывается к последнему сообщению.
        """
        if self._gemini is not None:
            try:
                return await self._chat_gemini(system, history, max_tokens, media)
            except Exception as exc:  # noqa: BLE001 — любой сбой Gemini → пробуем запасной вариант
                if media is not None:
                    raise AIError(f"Gemini не смог обработать вложение: {exc}") from exc
                logger.warning("Gemini недоступен (%s), переключаюсь на Pollinations", exc)
        if media is not None:
            raise AIError("Без ключа Gemini фото и голосовые не поддерживаются")
        return await self._chat_pollinations(system, history)

    async def _chat_gemini(
        self, system: str, history: list[tuple[str, str]], max_tokens: int, media: tuple[bytes, str] | None
    ) -> str:
        # сначала модель, которая отвечала последней, затем остальные по порядку
        order = ([self._working] if self._working else []) + [m for m in self.models if m != self._working]
        last_exc: Exception | None = None
        for model in order:
            try:
                text = await self._gemini_once(model, system, history, max_tokens, media)
                self._working = model
                return text
            except (AIError, asyncio.TimeoutError) as exc:
                logger.warning("Gemini %s: %s", model, exc)
                last_exc = exc
        raise AIError(f"Все модели Gemini недоступны: {last_exc}")

    async def _gemini_once(
        self,
        model: str,
        system: str,
        history: list[tuple[str, str]],
        max_tokens: int,
        media: tuple[bytes, str] | None = None,
    ) -> str:
        contents = [
            types.Content(role="model" if role == "model" else "user", parts=[types.Part.from_text(text=text)])
            for role, text in history
        ]
        if media is not None and contents:
            data, mime = media
            contents[-1].parts.insert(0, types.Part.from_bytes(data=data, mime_type=mime))
        use_thinking = model not in self._no_thinking
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens + (1024 if use_thinking else 0),
            temperature=0.9,
            # для переписки долгие размышления не нужны — так ответ приходит быстрее
            thinking_config=types.ThinkingConfig(thinking_level="LOW") if use_thinking else None,
        )
        try:
            resp = await asyncio.wait_for(
                self._gemini.aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=40 if media else 25,
            )
        except genai_errors.APIError as exc:
            if exc.code == 400 and use_thinking and "think" in str(exc.message).lower():
                self._no_thinking.add(model)
                return await self._gemini_once(model, system, history, max_tokens, media)
            raise AIError(f"Gemini API error {exc.code}: {exc.message}") from exc
        text = (resp.text or "").strip()
        if not text:
            raise AIError("Gemini вернул пустой ответ")
        return text

    async def _chat_pollinations(self, system: str, history: list[tuple[str, str]]) -> str:
        messages = [{"role": "system", "content": system}] + [
            {"role": "assistant" if role == "model" else "user", "content": text} for role, text in history
        ]
        session = await self._session()
        for attempt in range(2):
            try:
                async with session.post(
                    POLLINATIONS_TEXT_URL, json={"model": "openai", "messages": messages, "private": True}
                ) as resp:
                    if resp.status != 200:
                        raise AIError(f"Pollinations HTTP {resp.status}")
                    data = await resp.json(content_type=None)
                text = (data["choices"][0]["message"]["content"] or "").strip()
                if text:
                    return text
                raise AIError("Pollinations вернул пустой ответ")
            except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, AIError) as exc:
                logger.warning("Pollinations, попытка %s: %s", attempt + 1, exc)
                await asyncio.sleep(1.5)
        raise AIError("ИИ сейчас недоступен")

    async def to_image_prompt(self, text: str) -> str:
        """Переводит/улучшает описание картинки в короткий английский промпт."""
        try:
            result = await self.chat(
                "Convert the user's image request into one short, vivid English prompt for an image "
                "generator (max 60 words). Output only the prompt, no quotes.",
                [("user", text)],
                max_tokens=200,
            )
            return result.strip().strip('"')[:500] or text
        except AIError:
            return text
