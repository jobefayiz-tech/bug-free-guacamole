@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install -q requests pandas numpy
echo === PAPER trading (fake money, 20 USDT). Checks the market every hour. Close the window to stop. ===
%PY% crypto.py paper --loop 3600
pause
