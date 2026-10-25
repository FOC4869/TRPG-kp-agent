@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
backend\.venv\Scripts\python.exe run_web.py
pause
