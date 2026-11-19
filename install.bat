@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Установка TestTelegramBot ===

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -m venv .venv || py -3 -m venv .venv
) else (
    python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo [ОШИБКА] Не удалось создать виртуальное окружение. Установите Python 3.12+.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Создан файл .env — впишите в него BOT_TOKEN.
)

echo === Готово. Запуск: start.bat ===
pause
