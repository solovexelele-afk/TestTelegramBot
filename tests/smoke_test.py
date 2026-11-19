"""Офлайн-проверка: импорт, БД, ИИ (запасной провайдер), генерация картинки.

Запуск: .venv\\Scripts\\python.exe tests\\smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.__main__ import build_dispatcher  # noqa: E402
from bot.db import Database  # noqa: E402
from bot.services.ai import AIService  # noqa: E402
from bot.services.images import generate_image  # noqa: E402
from bot.services.personas import persona_prompt  # noqa: E402


async def main() -> None:
    dp = build_dispatcher()
    print("update types:", dp.resolve_used_update_types())

    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db = Database(f"sqlite+aiosqlite:///{tmp.as_posix()}")
    await db.init()
    await db.touch_user(1)
    await db.set_persona(1, "smart")
    assert (await db.touch_user(1)).persona == "smart"
    for i in range(70):
        await db.add_dialog("u:1", "user" if i % 2 == 0 else "model", f"msg {i}")
    hist = await db.history("u:1", 20)
    assert len(hist) == 20 and hist[-1][1] == "msg 69", hist[-3:]
    g = await db.toggle_group(-100, "antilink")
    assert g.antilink is False
    assert await db.add_warn(-100, 5) == 1 and await db.add_warn(-100, 5) == 2
    await db.count_message(-100, 5, "Вася")
    assert (await db.top(-100))[0].count == 1
    gw = await db.create_giveaway(-100, 5, "Приз", 1)
    assert (await db.join_giveaway(gw.id, 7, "Петя")) == (True, 1)
    assert (await db.join_giveaway(gw.id, 7, "Петя")) == (False, 1)
    winners = await db.draw_giveaway(gw.id)
    assert [w.user_id for w in winners] == [7]
    assert await db.draw_giveaway(gw.id) == []
    b = await db.upsert_business("c1", 42, "Артём", True, True)
    assert b.mode == "ai" and (await db.business_by_owner(42)).id == "c1"
    await db.mark_owner_active("c1", 9)
    assert await db.owner_recently_active("c1", 9, 15)
    assert not await db.owner_recently_active("c1", 10, 15)
    await db.close()
    print("db: OK")

    ai = AIService(os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "gemini-flash-latest"))
    print("ai provider:", ai.provider)
    answer = await ai.chat(persona_prompt("bro", "Тест"), [("user", "Привет! Скажи одно короткое предложение.")])
    print("ai answer:", answer[:200])
    prompt = await ai.to_image_prompt("кот-космонавт на Марсе")
    print("image prompt:", prompt[:200])
    await ai.close()

    data = await generate_image(prompt, 512, 512)
    print("image bytes:", len(data))
    print("ALL OK")


if __name__ == "__main__":
    asyncio.run(main())
