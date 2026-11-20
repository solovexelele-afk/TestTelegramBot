"""База данных (SQLAlchemy async).

Локально — SQLite в data/bot.db. На хостинге можно задать DATABASE_URL (PostgreSQL,
например бесплатный Neon), иначе данные живут до перезапуска инстанса.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    persona: Mapped[str] = mapped_column(String(32), default="bro")


class DialogMessage(Base):
    """История диалога с ИИ. scope: 'u:<user>' (личка), 'g:<chat>' (группа), 'b:<conn>:<chat>' (бизнес)."""

    __tablename__ = "dialog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(96), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | model
    text: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GroupSettings(Base):
    __tablename__ = "groups"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    welcome: Mapped[bool] = mapped_column(Boolean, default=True)
    antilink: Mapped[bool] = mapped_column(Boolean, default=True)
    antiflood: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_reply: Mapped[bool] = mapped_column(Boolean, default=True)
    warn_limit: Mapped[int] = mapped_column(Integer, default=3)


class Warn(Base):
    __tablename__ = "warns"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class ChatStat(Base):
    __tablename__ = "stats"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    count: Mapped[int] = mapped_column(Integer, default=0)


class Giveaway(Base):
    __tablename__ = "giveaways"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger)
    prize: Mapped[str] = mapped_column(String(256))
    winners: Mapped[int] = mapped_column(Integer, default=1)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)


class GiveawayEntry(Base):
    __tablename__ = "giveaway_entries"
    giveaway_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")


class BusinessConn(Base):
    __tablename__ = "business"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_name: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # подключение активно
    can_reply: Mapped[bool] = mapped_column(Boolean, default=True)
    mode: Mapped[str] = mapped_column(String(16), default="ai")  # off | away | ai
    away_text: Mapped[str] = mapped_column(Text, default="Привет! Сейчас не могу ответить, напишу позже 🙌")
    instructions: Mapped[str] = mapped_column(Text, default="")
    pause_minutes: Mapped[int] = mapped_column(Integer, default=15)


class OwnerActivity(Base):
    """Когда владелец бизнес-аккаунта сам последний раз писал в чат (чтобы не перебивать его)."""

    __tablename__ = "owner_activity"
    conn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    last: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StyleSample(Base):
    """Образец стиля владельца: его сообщение (me) и, если есть, на что он отвечал (them)."""

    __tablename__ = "style_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    them: Mapped[str] = mapped_column(Text, default="")
    me: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StyleProfile(Base):
    """Краткое описание стиля владельца, составленное ИИ по образцам."""

    __tablename__ = "style_profiles"
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str] = mapped_column(Text, default="")
    samples_at: Mapped[int] = mapped_column(Integer, default=0)  # сколько образцов было при составлении
    updated: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


STYLE_KEEP = 800  # сколько последних образцов храним на владельца


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite"):
            Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    # ---------- users ----------
    async def touch_user(self, user_id: int) -> User:
        async with self.session() as s:
            user = await s.get(User, user_id)
            if user is None:
                user = User(id=user_id)
                s.add(user)
                await s.commit()
            return user

    async def set_persona(self, user_id: int, persona: str) -> None:
        async with self.session() as s:
            user = await s.get(User, user_id) or User(id=user_id)
            user.persona = persona
            s.add(user)
            await s.commit()

    async def count_users(self) -> int:
        async with self.session() as s:
            return int(await s.scalar(select(func.count()).select_from(User)) or 0)

    # ---------- dialog ----------
    async def history(self, scope: str, limit: int) -> list[tuple[str, str]]:
        async with self.session() as s:
            rows = (
                await s.scalars(
                    select(DialogMessage)
                    .where(DialogMessage.scope == scope)
                    .order_by(DialogMessage.id.desc())
                    .limit(limit)
                )
            ).all()
        return [(r.role, r.text) for r in reversed(rows)]

    async def add_dialog(self, scope: str, role: str, text: str, keep: int = 60) -> None:
        async with self.session() as s:
            s.add(DialogMessage(scope=scope, role=role, text=text[:4000]))
            await s.flush()
            old_ids = (
                await s.scalars(
                    select(DialogMessage.id)
                    .where(DialogMessage.scope == scope)
                    .order_by(DialogMessage.id.desc())
                    .offset(keep)
                )
            ).all()
            if old_ids:
                await s.execute(delete(DialogMessage).where(DialogMessage.id.in_(old_ids)))
            await s.commit()

    async def clear_dialog(self, scope: str) -> None:
        async with self.session() as s:
            await s.execute(delete(DialogMessage).where(DialogMessage.scope == scope))
            await s.commit()

    # ---------- groups ----------
    async def group(self, chat_id: int) -> GroupSettings:
        async with self.session() as s:
            g = await s.get(GroupSettings, chat_id)
            if g is None:
                g = GroupSettings(chat_id=chat_id)
                s.add(g)
                await s.commit()
            return g

    async def toggle_group(self, chat_id: int, field_name: str) -> GroupSettings:
        await self.group(chat_id)  # создаёт запись с настройками по умолчанию
        async with self.session() as s:
            g = await s.get(GroupSettings, chat_id)
            setattr(g, field_name, not bool(getattr(g, field_name)))
            s.add(g)
            await s.commit()
            return g

    async def add_warn(self, chat_id: int, user_id: int) -> int:
        async with self.session() as s:
            w = await s.get(Warn, (chat_id, user_id)) or Warn(chat_id=chat_id, user_id=user_id, count=0)
            w.count += 1
            s.add(w)
            await s.commit()
            return w.count

    async def reset_warns(self, chat_id: int, user_id: int) -> None:
        async with self.session() as s:
            await s.execute(delete(Warn).where(Warn.chat_id == chat_id, Warn.user_id == user_id))
            await s.commit()

    async def count_message(self, chat_id: int, user_id: int, name: str) -> None:
        async with self.session() as s:
            st = await s.get(ChatStat, (chat_id, user_id)) or ChatStat(chat_id=chat_id, user_id=user_id, count=0)
            st.count += 1
            st.name = name[:128]
            s.add(st)
            await s.commit()

    async def top(self, chat_id: int, limit: int = 10) -> list[ChatStat]:
        async with self.session() as s:
            return list(
                (
                    await s.scalars(
                        select(ChatStat).where(ChatStat.chat_id == chat_id).order_by(ChatStat.count.desc()).limit(limit)
                    )
                ).all()
            )

    # ---------- giveaways ----------
    async def create_giveaway(self, chat_id: int, creator_id: int, prize: str, winners: int) -> Giveaway:
        async with self.session() as s:
            g = Giveaway(chat_id=chat_id, creator_id=creator_id, prize=prize[:256], winners=winners)
            s.add(g)
            await s.commit()
            return g

    async def get_giveaway(self, gid: int) -> Giveaway | None:
        async with self.session() as s:
            return await s.get(Giveaway, gid)

    async def join_giveaway(self, gid: int, user_id: int, name: str) -> tuple[bool, int]:
        """Возвращает (новый участник?, всего участников)."""
        async with self.session() as s:
            exists = await s.get(GiveawayEntry, (gid, user_id))
            if exists is None:
                s.add(GiveawayEntry(giveaway_id=gid, user_id=user_id, name=name[:128]))
                await s.commit()
            total = await s.scalar(
                select(func.count()).select_from(GiveawayEntry).where(GiveawayEntry.giveaway_id == gid)
            )
            return exists is None, int(total or 0)

    async def draw_giveaway(self, gid: int) -> list[GiveawayEntry]:
        async with self.session() as s:
            g = await s.get(Giveaway, gid)
            if g is None or g.finished:
                return []
            entries = list(
                (await s.scalars(select(GiveawayEntry).where(GiveawayEntry.giveaway_id == gid))).all()
            )
            g.finished = True
            await s.commit()
        return random.sample(entries, k=min(g.winners, len(entries)))

    # ---------- business ----------
    async def upsert_business(
        self, conn_id: str, owner_id: int, owner_name: str, enabled: bool, can_reply: bool
    ) -> BusinessConn:
        async with self.session() as s:
            b = await s.get(BusinessConn, conn_id)
            if b is None:
                b = BusinessConn(id=conn_id, owner_id=owner_id)
            b.owner_name = owner_name[:128]
            b.enabled = enabled
            b.can_reply = can_reply
            s.add(b)
            await s.commit()
            return b

    async def business(self, conn_id: str) -> BusinessConn | None:
        async with self.session() as s:
            return await s.get(BusinessConn, conn_id)

    async def business_by_owner(self, owner_id: int) -> BusinessConn | None:
        async with self.session() as s:
            return await s.scalar(
                select(BusinessConn).where(BusinessConn.owner_id == owner_id, BusinessConn.enabled.is_(True))
            )

    async def update_business(self, conn_id: str, **fields: object) -> BusinessConn | None:
        async with self.session() as s:
            b = await s.get(BusinessConn, conn_id)
            if b is None:
                return None
            for k, v in fields.items():
                setattr(b, k, v)
            await s.commit()
            return b

    async def mark_owner_active(self, conn_id: str, chat_id: int) -> None:
        async with self.session() as s:
            a = await s.get(OwnerActivity, (conn_id, chat_id)) or OwnerActivity(conn_id=conn_id, chat_id=chat_id)
            a.last = utcnow()
            s.add(a)
            await s.commit()

    async def owner_recently_active(self, conn_id: str, chat_id: int, minutes: int) -> bool:
        if minutes <= 0:
            return False
        async with self.session() as s:
            a = await s.get(OwnerActivity, (conn_id, chat_id))
            return a is not None and utcnow() - a.last < timedelta(minutes=minutes)

    # ---------- стиль владельца ----------
    async def add_style_samples(self, owner_id: int, items: list[tuple[str, str]]) -> int:
        """items: [(them, me)]. Возвращает, сколько всего образцов у владельца."""
        async with self.session() as s:
            for them, me in items:
                s.add(StyleSample(owner_id=owner_id, them=(them or "")[:500], me=me[:500]))
            await s.flush()
            old_ids = (
                await s.scalars(
                    select(StyleSample.id)
                    .where(StyleSample.owner_id == owner_id)
                    .order_by(StyleSample.id.desc())
                    .offset(STYLE_KEEP)
                )
            ).all()
            if old_ids:
                await s.execute(delete(StyleSample).where(StyleSample.id.in_(old_ids)))
            await s.commit()
            return int(
                await s.scalar(select(func.count()).select_from(StyleSample).where(StyleSample.owner_id == owner_id))
                or 0
            )

    async def count_style(self, owner_id: int) -> int:
        async with self.session() as s:
            return int(
                await s.scalar(select(func.count()).select_from(StyleSample).where(StyleSample.owner_id == owner_id))
                or 0
            )

    async def style_examples(self, owner_id: int, pairs: int = 25, singles: int = 25) -> list[tuple[str, str]]:
        """Случайная подборка: пары «им → я» и отдельные сообщения владельца."""
        async with self.session() as s:
            with_ctx = (
                await s.scalars(
                    select(StyleSample)
                    .where(StyleSample.owner_id == owner_id, StyleSample.them != "")
                    .order_by(func.random())
                    .limit(pairs)
                )
            ).all()
            alone = (
                await s.scalars(
                    select(StyleSample)
                    .where(StyleSample.owner_id == owner_id, StyleSample.them == "")
                    .order_by(func.random())
                    .limit(singles)
                )
            ).all()
        return [(x.them, x.me) for x in list(with_ctx) + list(alone)]

    async def clear_style(self, owner_id: int) -> None:
        async with self.session() as s:
            await s.execute(delete(StyleSample).where(StyleSample.owner_id == owner_id))
            await s.execute(delete(StyleProfile).where(StyleProfile.owner_id == owner_id))
            await s.commit()

    async def style_profile(self, owner_id: int) -> StyleProfile | None:
        async with self.session() as s:
            return await s.get(StyleProfile, owner_id)

    async def set_style_profile(self, owner_id: int, text: str, samples_at: int) -> None:
        async with self.session() as s:
            p = await s.get(StyleProfile, owner_id) or StyleProfile(owner_id=owner_id)
            p.text, p.samples_at, p.updated = text[:3000], samples_at, utcnow()
            s.add(p)
            await s.commit()
