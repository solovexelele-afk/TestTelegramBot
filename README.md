# TestTelegramBot

Тестовый Telegram-бот на **Python 3.12 + aiogram 3**.

Команды: `/start`, `/help`, `/id`, `/profile` + reply- и inline-кнопки.

## Структура

```
bot/
  __main__.py      точка входа (polling локально / webhook на хостинге)
  config.py        конфигурация из .env / переменных окружения
  logging_setup.py логирование (консоль + logs/bot.log)
  middlewares.py   логирование входящих апдейтов
  keyboards.py     клавиатуры
  texts.py         тексты сообщений
  storage.py       in-memory хранилище
  handlers/        common (/start, /help), user (/id, /profile), errors, fallback
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

* Автодеплой: каждый `git push` в ветку `main` запускает новый деплой.
* Переменные: `BOT_TOKEN` (вручную, секрет), `WEBHOOK_SECRET` (генерируется), `BOT_MODE=webhook`.
* `RENDER_EXTERNAL_URL` Render задаёт сам — по нему бот регистрирует webhook.
* Бесплатный инстанс засыпает через 15 мин без запросов; первое сообщение будит его (~30–60 с задержки).

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
