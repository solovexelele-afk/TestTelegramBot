"""Проверка разбора экспорта Telegram Desktop (без сети).

Запуск: .venv\\Scripts\\python.exe tests\\test_style.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services.style import ExportError, as_me_prompt, parse_export  # noqa: E402

OWNER = 111


def msg(i: int, who: int, text, ts: int, **extra) -> dict:
    return {
        "id": i,
        "type": "message",
        "date": "2026-11-01T12:00:00",
        "date_unixtime": str(ts),
        "from": "X",
        "from_id": f"user{who}",
        "text": text,
        **extra,
    }


single_chat = {
    "name": "Друг",
    "type": "personal_chat",
    "id": 222,
    "messages": [
        msg(1, 222, "го в кс вечером?", 1000),
        msg(2, OWNER, "ахахах го", 1060),
        msg(3, OWNER, "тока после 8", 1070),  # подряд — без контекста
        msg(4, 222, ["смотри ", {"type": "link", "text": "https://x.y"}], 2000),
        msg(5, OWNER, "кст норм тема)))", 2010),
        msg(6, 222, "ты где", 50000),
        msg(7, OWNER, "дома", 50000 + 7 * 3600),  # позже 6 часов — без контекста
        msg(8, OWNER, "https://only.link", 60000),  # только ссылка — пропускаем
        msg(9, OWNER, "переслал", 60010, forwarded_from="Канал"),  # пересланное — пропускаем
        {"id": 10, "type": "service", "action": "phone_call"},
    ],
}

samples = parse_export(json.dumps(single_chat, ensure_ascii=False).encode("utf-8"), OWNER)
assert samples == [
    ("го в кс вечером?", "ахахах го"),
    ("", "тока после 8"),
    ("смотри https://x.y", "кст норм тема)))"),
    ("", "дома"),
], samples

full_export = {"chats": {"list": [single_chat, {"type": "public_channel", "messages": [msg(1, OWNER, "пост", 1)]}]}}
assert len(parse_export(json.dumps(full_export).encode("utf-8-sig"), OWNER)) == 4  # канал пропущен

for bad in (b"not json", b"[1,2]", json.dumps({"foo": 1}).encode()):
    try:
        parse_export(bad, OWNER)
        raise AssertionError("ожидалась ошибка")
    except ExportError:
        pass

prompt = as_me_prompt("Артём", "пишет с маленькой", samples, "учусь в 10 классе", contact="Ирина", family=True)
assert "ты — Артём" in prompt and "им: го в кс вечером?\n  ты: ахахах го" in prompt and "учусь в 10 классе" in prompt
assert "родственник" in prompt and "без мата" in prompt
assert "незнакомый" in as_me_prompt("A", "", [], "", first_contact=True)

from bot.services.style import FAMILY_RE, asks_if_bot, strip_disclosure  # noqa: E402

assert FAMILY_RE.search("Мама") and FAMILY_RE.search("мамуля ❤") and not FAMILY_RE.search("Мила")
assert strip_disclosure(["Та норм всё", "автоответчик @vexelele имба", "это автоответчик если что)", "Ало"], "vexelele") == [
    "Та норм всё", "Ало"]
assert asks_if_bot("как будто я ролю с каким то ботом") and not asks_if_bot("го гулять")
print("style parsing: OK")
