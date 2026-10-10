@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_python.bat" || exit /b 1
%PY% -m pip install -q requests pandas numpy
echo === PAPER trading (fake money, 1000 USDT). Checks the market every hour. Close the window to stop. ===
%PY% crypto.py paper --top 15 --loop 3600
pause
