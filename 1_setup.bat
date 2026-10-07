@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH". & pause & exit /b 1)
echo === Installing packages (a few minutes) ===
%PY% -m pip install -r requirements.txt
if errorlevel 1 (echo Install failed. & pause & exit /b 1)
echo.
echo === Alpaca PAPER keys (paste each one, then press Enter) ===
set /p KEYID=Key ID: 
set /p SECRET=Secret: 
(
echo ALPACA_API_KEY=%KEYID%
echo ALPACA_SECRET=%SECRET%
) > .env
echo.
echo Saved to .env on this computer only. Now run 2_test.bat
pause
