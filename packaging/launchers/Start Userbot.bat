@echo off
rem Starts Telegram Userbot (Windows).
rem
rem The first start downloads Python and the libraries the bot needs (about
rem 100 MB) into the runtime folder next to this file. Nothing is installed
rem system-wide: deleting this folder removes it all. Your settings, prompts and
rem Telegram login are kept separately (see "Open data folder" in the menu).
rem
rem Any arguments are passed on, e.g.:  "Start Userbot.bat" doctor
setlocal
chcp 65001 >nul
title Telegram Userbot

set "DIR=%~dp0"
set "UV_PYTHON_INSTALL_DIR=%DIR%runtime\python"
set "UV_CACHE_DIR=%DIR%runtime\cache"
set "UV_PROJECT_ENVIRONMENT=%DIR%runtime\venv"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_NO_CONFIG=1"
set "PYTHONUTF8=1"

if not exist "%DIR%runtime\venv" echo First start: downloading Python and the bot's libraries (about 100 MB, once)...

"%DIR%runtime\bin\uv.exe" run --frozen --no-dev --python 3.13 --directory "%DIR%app" python -m userbot %*
if errorlevel 1 (
    echo.
    echo Something went wrong. The message above says what. Logs are in the data folder's logs folder.
    pause
)
endlocal
