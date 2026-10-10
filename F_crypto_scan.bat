@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_python.bat" || exit /b 1
%PY% -m pip install -q requests pandas numpy
echo === Scanning the 25 most liquid coins: what would the team buy today? ===
%PY% crypto.py scan --top 25
echo.
echo Copy everything above and send it to Claude.
pause
