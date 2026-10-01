@echo off
rem Starts the live master monitor and opens it in your browser.
rem Bitwig must be on a "Windows Audio" (WASAPI) driver so its output can be captured.
cd /d "%~dp0"
echo Live master monitor: http://127.0.0.1:8780   (close this window to stop it)
start "" "http://127.0.0.1:8780"
python live_monitor.py --port 8780
pause
