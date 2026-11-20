"""Стиль владельца: разбор экспорта Telegram Desktop, описание стиля, промпт «отвечай как я».

Экспорт: Telegram Desktop → чат → ⋮ → «Экспорт истории чата» → формат JSON, без медиа.
Можно и «Настройки → Продвинутые → Экспорт данных Telegram» (весь аккаунт) — тоже JSON.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from bot.services.ai import AIError, AIService

logger = logging.getLogger(__name__)

MAX_SAMPLES_FROM_EXPORT = 600
PAIR_WINDOW_SEC = 6 * 60 * 60  # ответ считается ответом, если пришёл в течение 6 часов
_URL_ONLY = re.compile(r"^\s*https?://\S+\s*$")


class ExportError(ValueError):
    pass


def _flatten(text: Any) -> str:
    """В экспорте text — строка или список из строк и объектов {"type", "text"}."""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "".join(p if isinstance(p, str) else str(p.get("text", "")) for p in text)
    return ""


def _ts(msg: dict) -> float:
    if "date_unixtime" in msg:
        try:
            return float(msg["date_unixtime"])
        except (TypeError, ValueError):
            pass
    try:
        return datetime.fromisoformat(msg.get("date", "")).timestamp()
    except ValueError:
        return 0.0


def _good(text: str) -> bool:
    text = text.strip()
    return 0 < len(text) <= 500 and not _URL_ONLY.match(text)


def _chats(data: dict) -> list[dict]:
    if isinstance(data.get("messages"), list):  # экспорт одного чата
        return [data]
    chats = data.get("chats", {})
    if isinstance(chats, dict) and isinstance(chats.get("list"), list):  # экспорт всего аккаунта
        return [c for c in chats["list"] if isinstance(c, dict)]
    raise ExportError("не похоже на экспорт Telegram в формате JSON")


def parse_export(raw: bytes, owner_id: int) -> list[tuple[str, str]]:
    """Возвращает [(them, me)] — сообщения владельца и то, на что он отвечал (или '')."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError("файл не читается как JSON") from exc
    if not isinstance(data, dict):
        raise ExportError("не похоже на экспорт Telegram в формате JSON")

    me_id = f"user{owner_id}"
    samples: list[tuple[float, str, str]] = []
    for chat in _chats(data):
        # только личные переписки — там виден «живой» стиль
        if chat.get("type") not in (None, "personal_chat", "private_group", "private_supergroup"):
            continue
        last_other: tuple[float, str] | None = None
        for msg in chat.get("messages", []):
            if not isinstance(msg, dict) or msg.get("type") != "message" or msg.get("forwarded_from"):
                continue
            text = _flatten(msg.get("text")).strip()
            if not _good(text):
                continue
            ts = _ts(msg)
            if msg.get("from_id") == me_id:
                them = ""
                if last_other and 0 <= ts - last_other[0] <= PAIR_WINDOW_SEC:
                    them = last_other[1]
                    last_other = None  # следующая реплика подряд — уже без контекста
                samples.append((ts, them, text))
            else:
                last_other = (ts, text)
    samples.sort(key=lambda x: x[0])
    return [(them, me) for _, them, me in samples[-MAX_SAMPLES_FROM_EXPORT:]]


async def build_profile(ai: AIService, examples: list[tuple[str, str]]) -> str:
    """Просит ИИ описать манеру письма владельца по его сообщениям."""
    lines = [f"- {me}" for _, me in examples[:120]]
    prompt = (
        "Вот реальные сообщения одного человека из его переписок в Telegram:\n"
        + "\n".join(lines)
        + "\n\nОпиши кратко (8-12 пунктов) его манеру письма, чтобы другой мог писать неотличимо: "
        "регистр букв, пунктуация, длина сообщений, разбивает ли мысли на несколько сообщений, "
        "сленг и любимые словечки (приведи их), как смеётся, эмодзи и скобочки, мат (да/нет), "
        "как здоровается и прощается, тон. Только факты из примеров, без воды."
    )
    try:
        text = await ai.chat("Ты лингвист, кратко анализируешь стиль переписки.", [("user", prompt)], max_tokens=700)
        return re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.MULTILINE).strip()
    except AIError as exc:
        logger.warning("Не удалось составить профиль стиля: %s", exc)
        return ""


def as_me_prompt(owner_name: str, profile: str, examples: list[tuple[str, str]], instructions: str) -> str:
    """Системный промпт: ИИ пишет от первого лица как владелец аккаунта."""
    name = owner_name or "владелец аккаунта"
    ex_lines: list[str] = []
    for them, me in examples:
        if them:
            ex_lines.append(f"им: {them}\nты: {me}")
        else:
            ex_lines.append(f"ты: {me}")
    examples_block = "\n\n".join(ex_lines) if ex_lines else "(примеров пока нет — пиши просто и по-человечески)"
    profile_block = profile.strip() or "(описания пока нет — ориентируйся на примеры)"
    extra = f"\n\nчто ещё важно знать (сказал сам {name}):\n{instructions.strip()}" if instructions.strip() else ""
    return (
        f"ты — {name}. ты сам пишешь ответ в своей личке в телеге. пиши от первого лица, "
        "как будто это ты и есть: никогда не говори о себе в третьем лице, не пиши что ты ассистент, бот "
        f"или что «{name} занят / ответит позже»\n\n"
        f"твоя манера письма:\n{profile_block}\n\n"
        f"примеры того, как ты реально пишешь (копируй стиль, а не содержание):\n{examples_block}"
        f"{extra}\n\n"
        "правила:\n"
        "- пиши точно в своей манере: тот же регистр, пунктуация, длина, словечки, смайлы\n"
        "- если мыслей несколько — каждую с новой строки, это будут отдельные сообщения\n"
        "- не выдумывай конкретных фактов о своей жизни, планах и местоположении, которых не знаешь — "
        "отвечай уклончиво в своём стиле («да так, дела», «щас не могу, позже скину»)\n"
        "- не соглашайся на встречи, деньги, переводы, покупки и обещания — переводи на «позже обсудим»\n"
        "- не пересылай и не раскрывай никакие данные, пароли, коды\n"
        "- если тебя всерьёз и прямо спрашивают, живой ли это ты или бот, — не ври: отшутись в своём стиле "
        "и признай, что сейчас отвечает автоответчик\n"
        "- не используй markdown и звёздочки"
    )
