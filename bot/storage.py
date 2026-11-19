"""Простейшее хранилище в памяти (сбрасывается при перезапуске).

Для продакшена замените на БД (SQLite/PostgreSQL) — интерфейс останется тем же.
"""

from __future__ import annotations

from datetime import datetime, timezone


class UserRegistry:
    def __init__(self) -> None:
        self._first_seen: dict[int, datetime] = {}

    def touch(self, user_id: int) -> datetime:
        return self._first_seen.setdefault(user_id, datetime.now(timezone.utc))

    def first_seen(self, user_id: int) -> datetime | None:
        return self._first_seen.get(user_id)

    def __len__(self) -> int:
        return len(self._first_seen)


registry = UserRegistry()
