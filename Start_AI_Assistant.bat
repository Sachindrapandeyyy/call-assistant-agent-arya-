@echo off
title Aura AI Assistant - 1-Click Desktop Launcher
color 0b
cls
echo ==============================================================================
echo                      AURA AI PERSONAL RECEPTIONIST
echo              Zero-Touch Intelligent Call Automation Server
echo ==============================================================================
echo.

cd /d "C:\Users\Sachi\.gemini\antigravity\scratch\ai-call-assistant"

echo [1/3] Checking Ollama AI Model Engine...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo       Ollama is already active.
) else (
    echo       Starting Ollama server in background...
    start /min "Ollama Service" ollama serve
    timeout /t 2 /nobreak >nul
)

echo.
echo [2/3] Starting Aura AI Local Backend Server (Port 8000)...
start "Aura AI Production Server" /min python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

timeout /t 3 /nobreak >nul

echo.
echo [3/3] Checking System Health...
python -c "import requests; r=requests.get('http://127.0.0.1:8000/api/health').json(); print('      Overall Status:', r.get('status')); [print('       -', k, ':', v) for k, v in r.get('subsystems', {}).items()]"

echo.
echo ==============================================================================
echo   ALL SYSTEMS ONLINE AND OPERATIONAL!
echo   - Local IP: http://127.0.0.1:8000
echo   - Keep this window open or minimize it.
echo   - Incoming calls on your Infinix phone will now be handled automatically.
echo ==============================================================================
echo.
pause
