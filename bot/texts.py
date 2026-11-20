"""Тексты сообщений (HTML-разметка)."""

from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.types import Chat, User

from bot.services.personas import PERSONAS


def start_text(user: User) -> str:
    return (
        f"👋 Привет, <b>{escape(user.first_name)}</b>!\n\n"
        "Я — бот-друг с ИИ. Что умею:\n"
        "💬 <b>Болтать</b> — пиши как другу, я помню наш диалог\n"
        "📸 <b>Смотреть фото и слушать гс</b> — кидай фотки, голосовые, кружки, стикеры\n"
        "🎨 <b>Рисовать</b> — просто напиши «нарисуй …» или /img\n"
        "👥 <b>Следить за группой</b> — антиспам, приветствия, розыгрыши, статистика\n"
        "💼 <b>Автоответчик</b> — отвечаю за тебя в личке через Telegram Business\n\n"
        "Всё бесплатно. Список команд — /help"
    )


HELP_TEXT = (
    "📖 <b>Команды</b>\n\n"
    "<b>Личный чат</b>\n"
    "просто текст — общение с ИИ\n"
    "фото, голосовые, кружки, стикеры — ИИ их понимает\n"
    "«нарисуй …» или /img <i>описание</i> — картинка\n"
    "  добавь «на телефон» — вертикальная, «на пк» — горизонтальная\n"
    "/persona — выбрать характер ИИ\n"
    "/reset — забыть диалог\n"
    "/profile — профиль, /id — ваш ID\n"
    "/business — настройки автоответчика\n\n"
    "<b>В группе</b> (боту нужны права администратора)\n"
    "обращение «@бот …» или ответ на сообщение бота — ИИ-ответ\n"
    "/settings — включить/выключить функции\n"
    "/warn, /mute [мин], /unmute, /ban — ответом на сообщение\n"
    "/stats — топ активных участников\n"
    "/giveaway [победителей] приз — розыгрыш\n"
    "/img <i>описание</i> — картинка прямо в чат"
)

GROUPS_TEXT = (
    "👥 <b>Бот для группы</b>\n\n"
    "1. Добавьте меня в группу.\n"
    "2. Сделайте администратором (удаление сообщений и блокировка участников).\n"
    "3. Напишите в группе /settings.\n\n"
    "Что я делаю: приветствую новых участников, удаляю ссылки от обычных участников, "
    "глушу флудеров, выдаю предупреждения, провожу розыгрыши, считаю активность "
    "и отвечаю с ИИ, если ко мне обратиться."
)

BUSINESS_HOWTO = (
    "💼 <b>Автоответчик через Telegram Business</b>\n\n"
    "Нужен <b>Telegram Premium</b> на вашем аккаунте.\n"
    "1. Настройки → <b>Telegram для бизнеса</b> → <b>Чат-боты</b>.\n"
    "2. Введите имя этого бота и выберите, в каких чатах он отвечает.\n"
    "3. Разрешите боту <b>отвечать на сообщения</b>.\n\n"
    "После подключения я пришлю сюда настройки: ИИ-ответы или шаблон, инструкции, "
    "пауза, если вы сами ответили в чате."
)

IMAGE_ASK = (
    "🎨 что нарисовать? опиши одним сообщением\n"
    "например: <i>кот-космонавт на марсе, аниме, обои на телефон</i>"
)
IMAGE_WAIT = "🎨 Рисую… обычно это 10–30 секунд"
IMAGE_FAIL = "😔 Не получилось нарисовать. Попробуйте ещё раз или измените описание."
AI_FAIL = "😔 ИИ сейчас перегружен. Попробуйте через минуту."
ERROR_TEXT = "⚠️ Произошла ошибка. Попробуйте ещё раз чуть позже."
NON_TEXT = "Я пока понимаю только текст 🙂 Напиши словами!"


def id_text(user: User, chat: Chat) -> str:
    return (
        "🆔 <b>Идентификаторы</b>\n\n"
        f"Ваш ID: <code>{user.id}</code>\n"
        f"ID чата: <code>{chat.id}</code>\n"
        f"Тип чата: <i>{escape(chat.type)}</i>\n\n"
        "<i>Нажмите на число, чтобы скопировать.</i>"
    )


def profile_text(user: User, first_seen: datetime | None, persona: str, provider: str) -> str:
    username = f"@{escape(user.username)}" if user.username else "—"
    premium = "✅ да" if user.is_premium else "❌ нет"
    seen = first_seen.strftime("%d.%m.%Y %H:%M UTC") if first_seen else "—"
    persona_title = PERSONAS.get(persona, PERSONAS["bro"])[0]
    return (
        "👤 <b>Ваш профиль</b>\n\n"
        f"<b>Имя:</b> {escape(user.full_name)}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Язык:</b> {escape(user.language_code or '—')}\n"
        f"<b>Telegram Premium:</b> {premium}\n"
        f"<b>С ботом с:</b> {seen}\n"
        f"<b>Характер ИИ:</b> {persona_title}\n"
        f"<b>Нейросеть:</b> {escape(provider)}"
    )


STYLE_HOWTO = (
    "📥 <b>Как научить меня твоему стилю</b>\n\n"
    "1. Открой <b>Telegram Desktop</b> на компьютере.\n"
    "2. Зайди в переписку с другом, где ты много пишешь → ⋮ → <b>Экспорт истории чата</b>.\n"
    "3. Сними все галочки с фото/видео/файлов, формат — <b>JSON</b> (машиночитаемый), нажми «Экспортировать».\n"
    "4. Пришли сюда файл <code>result.json</code> из папки экспорта.\n\n"
    "Можно прислать несколько чатов — чем больше твоих сообщений, тем точнее копия. "
    "Ещё я учусь сам: каждое сообщение, которое ты пишешь в подключённых чатах, запоминаю как образец.\n\n"
    "🔒 Я сохраняю только тексты твоих сообщений и фразы, на которые ты отвечал. "
    "Сбросить всё — кнопка «Забыть мой стиль»."
)
STYLE_MIRROR_ON = (
    "\n\n🪞 Теперь и в обычной переписке со мной я пишу как ты. "
    "Вернуть другой характер — /persona"
)
STYLE_NOT_JSON ="Пришли файл <code>result.json</code> — экспорт чата из Telegram Desktop в формате JSON.\n\n" + STYLE_HOWTO
STYLE_TOO_BIG = (
    "Файл больше 20 МБ — Telegram не даёт ботам скачивать такие. "
    "Экспортируй один-два чата без медиа, они весят меньше."
)
STYLE_NO_OWN = (
    "😕 В этом файле не нашлось твоих сообщений. Проверь, что это экспорт именно твоего аккаунта "
    "и личной переписки в формате JSON.\n\n" + STYLE_HOWTO
)


def style_status(count: int, profile: str) -> str:
    if count == 0:
        return "🧬 <b>Мой стиль</b>\n\nЯ пока не знаю, как ты пишешь.\n\n" + STYLE_HOWTO
    desc = escape(profile) if profile else "<i>описание появится, когда наберётся хотя бы 10 сообщений</i>"
    return (
        f"🧬 <b>Мой стиль</b>\n\nИзучено твоих сообщений: <b>{count}</b>\n\n"
        f"<b>Как ты пишешь:</b>\n{desc}\n\n"
        "Можешь прислать ещё экспорт чата (<code>result.json</code>), чтобы копия была точнее."
    )


def business_status(b, style_count: int = 0) -> str:  # b: BusinessConn | None
    style_line = f"\n\n🧬 Изучено твоих сообщений: <b>{style_count}</b>" if style_count else (
        "\n\n🧬 Стиль ещё не изучен — нажми «Мой стиль», чтобы я писал как ты"
    )
    if b is None:
        return BUSINESS_HOWTO + style_line
    modes = {"ai": "🤖 ИИ отвечает как вы, от вашего имени", "away": "📝 отправляется шаблон", "off": "⏸ выключен"}
    reply = "✅" if b.can_reply else "❌ (разрешите в настройках Telegram Business)"
    instr = escape(b.instructions) if b.instructions else "<i>не заданы</i>"
    return (
        "💼 <b>Автоответчик подключён</b>\n\n"
        f"<b>Режим:</b> {modes.get(b.mode, b.mode)}\n"
        f"<b>Право отвечать:</b> {reply}\n"
        f"<b>Пауза:</b> не отвечаю {b.pause_minutes} мин после вашего сообщения в чате\n"
        f"<b>Шаблон:</b> {escape(b.away_text)}\n"
        f"<b>Что ИИ знает о тебе:</b> {instr}"
        f"{style_line}"
    )
