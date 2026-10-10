@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install -q requests pandas numpy
echo === Paper result vs just holding BTC ===
%PY% crypto.py report
pause
