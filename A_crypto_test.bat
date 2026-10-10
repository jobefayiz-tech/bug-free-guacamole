@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install -q requests pandas numpy
echo === Binance team: backtest on real public data (no account needed) ===
%PY% crypto.py backtest
echo.
echo Copy everything above and send it to Claude.
pause
