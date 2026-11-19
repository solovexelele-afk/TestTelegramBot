@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TestTelegramBot

if not exist ".venv\Scripts\python.exe" (
    echo Виртуальное окружение не найдено. Сначала запустите install.bat
    pause
    exit /b 1
)
if not exist ".env" (
    echo Файл .env не найден. Скопируйте .env.example в .env и укажите BOT_TOKEN.
    pause
    exit /b 1
)

echo Запуск бота... (Ctrl+C или stop.bat для остановки)
".venv\Scripts\python.exe" -m bot
echo Бот завершил работу.
pause
