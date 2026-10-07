@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
echo === Daily trend portfolio (SPY, QQQ, TLT, GLD) vs buy-and-hold, ~6 years ===
%PY% main.py backtest --trend --exchange alpaca
echo.
echo Copy everything above and send it to Claude.
pause
