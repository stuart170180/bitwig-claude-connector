@echo off
rem Double-click to install the Bitwig connector for Claude (see README.md).
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python scripts\install.py %*
echo.
pause
