@echo off
cd /d "%~dp0"
python tools\publish.py %*
echo.
pause
