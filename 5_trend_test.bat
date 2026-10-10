@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_python.bat" || exit /b 1
echo === Daily trend portfolio (SPY, QQQ, TLT, GLD) vs buy-and-hold, ~6 years ===
%PY% main.py backtest --trend --exchange alpaca
echo.
echo Copy everything above and send it to Claude.
pause
