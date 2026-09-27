@echo off
cd /d "%~dp0"
echo Starting http://127.0.0.1:3000 ...
".venv\Scripts\python.exe" start_web.py
pause
