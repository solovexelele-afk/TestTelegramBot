@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "bot.pid" (
    echo Бот не запущен ^(файл bot.pid не найден^).
    timeout /t 3 >nul
    exit /b 0
)

set /p BOTPID=<bot.pid
taskkill /PID %BOTPID% /T /F >nul 2>nul
if errorlevel 1 (
    echo Процесс %BOTPID% не найден — вероятно, бот уже остановлен.
) else (
    echo Бот остановлен ^(PID %BOTPID%^).
)
del /q bot.pid >nul 2>nul
timeout /t 3 >nul
