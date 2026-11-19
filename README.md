# TestTelegramBot

Бот-друг с ИИ на **Python 3.12 + aiogram 3**. Всё на бесплатных сервисах.

* 💬 **ИИ-собеседник** с памятью диалога и 4 характерами (`/persona`, `/reset`) — Google Gemini
  (бесплатный ключ), запасной вариант без ключа — Pollinations.
  Пишет как живой человек: с маленькой буквы, со сленгом, несколькими сообщениями, ставит реакции.
  Новое сообщение или команда обрывает недосланный «хвост» старого ответа.
* 📸 **Понимает фото, голосовые, кружки и стикеры** (через Gemini).
* 🎨 **Генерация картинок** — «нарисуй …» прямо в чате или `/img описание` (бесплатный Pollinations,
  без водяного знака, 1 картинка в 45 с). «на телефон» → 9:16, «на пк» → 16:9.
* 👥 **Группы** — приветствие, антиссылки, антифлуд, `/warn` `/mute` `/unmute` `/ban`,
  `/stats`, розыгрыши `/giveaway`, ИИ-ответы по упоминанию; настройки `/settings`.
* 💼 **Telegram Business автоответчик** — ИИ или шаблон, инструкции, пауза после ответа владельца
  (`/business`; у владельца нужен Telegram Premium, у бота — Secretary/Business Mode в BotFather).

## Структура

```
bot/
  __main__.py      точка входа (polling локально / webhook на хостинге, keep-alive)
  config.py        конфигурация из .env / переменных окружения
  db.py            база данных (SQLite локально, PostgreSQL по DATABASE_URL)
  logging_setup.py логирование (консоль + logs/bot.log)
  middlewares.py   логирование входящих апдейтов
  keyboards.py     клавиатуры
  texts.py         тексты сообщений
  services/        ai (Gemini + запасной Pollinations), images, personas
  handlers/        common, draw, business, group, ai_chat, errors
tests/smoke_test.py  офлайн-проверка БД, ИИ и картинок
install.bat / start.bat / stop.bat   — локальный запуск на Windows
render.yaml                          — деплой на Render (Blueprint)
Procfile                             — для Railway/Heroku-подобных платформ
```

## Локальный запуск (Windows)

1. `install.bat` — создаст `.venv`, установит зависимости, создаст `.env`.
2. Впишите `BOT_TOKEN` в `.env`.
3. `start.bat` — запуск, `stop.bat` — остановка.

> ⚠️ Локальный запуск (polling) снимает webhook — пока бот запущен на ПК,
> облачная версия не получает сообщения. После `stop.bat` перезапустите сервис на Render
> (Manual Deploy → Restart), чтобы он снова установил webhook.

## Хостинг: Render (Free Web Service, режим webhook)

* Сервис: https://testtelegrambot-ag9s.onrender.com (health: `/health`).
* Автодеплой: каждый `git push` в ветку `main` запускает новый деплой (Auto-Deploy: On Commit).
  GitHub Actions (`.github/workflows/deploy.yml`) дополнительно проверяет, что код собирается.
* Переменные: `BOT_TOKEN` и `GEMINI_API_KEY` (вручную, секреты), `WEBHOOK_SECRET` (генерируется),
  `BOT_MODE=webhook`, `KEEP_ALIVE=true`, необязательно `DATABASE_URL`.
* `RENDER_EXTERNAL_URL` Render задаёт сам — по нему бот регистрирует webhook.
* `KEEP_ALIVE=true` — бот пингует свой `/health` каждые 10 мин, чтобы бесплатный инстанс не засыпал
  (750 бесплатных часов в месяц хватает на 24/7).
* Без `DATABASE_URL` данные (история, настройки групп, розыгрыши) хранятся в SQLite и сбрасываются
  при каждом деплое. Для постоянного хранения подключите бесплатный PostgreSQL (например, Neon).

## Обновление бота

```powershell
git add -A
git commit -m "Описание изменений"
git push
```

Render сам соберёт и перезапустит бота (Dashboard → Events/Logs).

## Перезапуск

* Облако: Render Dashboard → сервис `testtelegrambot` → **Manual Deploy → Restart service**
  (или **Deploy latest commit**).
* Локально: `stop.bat`, затем `start.bat`.
