@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install -q requests pandas numpy
echo === What every specialist says about each coin RIGHT NOW ===
%PY% crypto.py status
echo.
echo Copy everything above and send it to Claude.
pause
