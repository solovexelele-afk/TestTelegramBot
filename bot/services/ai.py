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
    def __init__(self, gemini_api_key: str, gemini_model: str) -> None:
        self.gemini_model = gemini_model
        self._gemini = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
        self._http: aiohttp.ClientSession | None = None

    @property
    def provider(self) -> str:
        return f"Gemini ({self.gemini_model})" if self._gemini else "Pollinations (без ключа)"

    async def _session(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()

    async def chat(self, system: str, history: list[tuple[str, str]], max_tokens: int = 1024) -> str:
        """history: [(role, text)], role = 'user' | 'model'. Последний элемент — новое сообщение."""
        if self._gemini is not None:
            try:
                return await self._chat_gemini(system, history, max_tokens)
            except Exception as exc:  # noqa: BLE001 — любой сбой Gemini → пробуем запасной вариант
                logger.warning("Gemini недоступен (%s), переключаюсь на Pollinations", exc)
        return await self._chat_pollinations(system, history)

    async def _chat_gemini(self, system: str, history: list[tuple[str, str]], max_tokens: int) -> str:
        contents = [
            types.Content(role="model" if role == "model" else "user", parts=[types.Part.from_text(text=text)])
            for role, text in history
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.9,
        )
        try:
            resp = await asyncio.wait_for(
                self._gemini.aio.models.generate_content(
                    model=self.gemini_model, contents=contents, config=config
                ),
                timeout=60,
            )
        except genai_errors.APIError as exc:
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
