"""Проверка разбора запросов и постобработки ответов (без сети).

Запуск: .venv\\Scripts\\python.exe tests\\test_text_logic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.handlers.draw import image_intent  # noqa: E402
from bot.services.images import detect_format  # noqa: E402
from bot.services.personas import extract_reaction, extract_transcript, humanize  # noqa: E402

CASES_INTENT = {
    "нарисуй кота в очках": "кота в очках",
    "Нарисуй мне собаку": "собаку",
    "бро нарисуй закат": "закат",
    "сгенерируй аватарку в стиле аниме": "аватарку в стиле аниме",
    "сделай аватарку с котом": "аватарку с котом",
    "нарисуй картинку горы на пк": "горы на пк",
    "сделай обои на телефон с космосом": "обои на телефон с космосом",
    "сделай картинку с драконом": "с драконом",
    "скинь фото кота": "кота",
    "сделай мне домашку": None,
    "покажи что умеешь": None,
    "я нарисовал кота": None,
    "привет как дела": None,
    "нарисуй": None,
}
for text, expected in CASES_INTENT.items():
    got = image_intent(text)
    assert got == expected, (text, got, expected)

assert detect_format("кот обои на телефон")[:2] == (768, 1344)
assert detect_format("закат вертикальная")[:2] == (768, 1344)
assert detect_format("горы на пк")[:2] == (1344, 768)
assert detect_format("баннер для канала")[:2] == (1344, 768)
assert detect_format("просто кот")[:2] == (1024, 1024)

assert extract_reaction("[r:🔥] ахахах имба") == ("🔥", "ахахах имба")
assert extract_reaction("[r:❤️] норм") == (None, "норм")  # не из списка — без реакции
assert extract_reaction("просто текст") == (None, "просто текст")
assert humanize("[r:😁] Ору.\nНу ты даёшь") == ["ору", "ну ты даёшь"]
assert extract_transcript("TRANSCRIPT: привет как дела\nздарова, норм") == ("привет как дела", "здарова, норм")
assert extract_transcript("без транскрипта") == (None, "без транскрипта")
print("text logic: OK")
