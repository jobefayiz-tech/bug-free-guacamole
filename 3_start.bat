@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH". & pause & exit /b 1)
echo === Starting the agent on the Alpaca PAPER account (fake money) ===
echo Keep this window open during US market hours. Close it to stop.
%PY% main.py live --exchange alpaca --symbols AAPL,MSFT,NVDA,AMZN,GOOGL --interval 300
pause
