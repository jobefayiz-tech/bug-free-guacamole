@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_python.bat" || exit /b 1
%PY% -m pip install -q requests pandas numpy
echo === PAPER trading (fake money, 20 USDT). Checks the market every hour. Close the window to stop. ===
%PY% crypto.py paper --loop 3600
pause
