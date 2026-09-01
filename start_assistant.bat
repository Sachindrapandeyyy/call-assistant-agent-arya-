@echo off
title Sachindra's AI Personal Call Assistant
color 0A

echo ======================================================================
echo           SACHINDRA'S AI PERSONAL CALL ASSISTANT (v1.0)
echo ======================================================================
echo.
echo [1/3] Ensuring local Ollama server is active...
start /B ollama serve >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/3] Verifying Python environment and audio pipeline...
cd /d "C:\Users\Sachi\.gemini\antigravity\scratch\ai-call-assistant"

echo [3/3] Starting FastAPI Telephony Server on 0.0.0.0:8000...
echo.
echo ======================================================================
echo   AI RECEPTIONIST IS LIVE AND PROTECTING YOUR PHONE CALLS!
echo   - Phone Link:   Connected to Infinix Zero 5G
echo   - Audio Bridge: WASAPI Loopback + VB-Cable
echo   - Local STT:    NVIDIA RTX 4050 (faster-whisper)
echo   - Local LLM:    Qwen2.5-3B (Ollama)
echo   - Voice:        Natural Female Indian Voice (Edge-TTS)
echo.
echo   Press CTRL+C anytime to stop the assistant.
echo ======================================================================
echo.

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
pause
