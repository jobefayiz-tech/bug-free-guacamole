@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH". & pause & exit /b 1)
echo === Agent vs SPY benchmark ===
%PY% main.py report --benchmark SPY
pause
