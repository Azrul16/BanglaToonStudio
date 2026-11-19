@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create a Python 3.11 virtual environment and install requirements.txt first.
  echo See README.md for setup commands.
  pause
  exit /b 1
)
if exist "Bangla Toon Studio.exe" (
  "Bangla Toon Studio.exe"
) else (
  ".venv\Scripts\python.exe" scripts\desktop_launcher.py
)
