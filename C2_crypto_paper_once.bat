@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_python.bat" || exit /b 1
%PY% -m pip install -q requests pandas numpy
echo === PAPER trading, one check now (fake money). Run once a day, after the daily candle closes (03:00 Saudi time). ===
%PY% crypto.py paper --top 15
echo.
echo Your fake account is saved in paper_state.json in THIS folder. Do not delete it.
pause
