@echo off
title Stop Aura AI Assistant
color 0c
cls
echo ==============================================================================
echo                      STOPPING AURA AI ASSISTANT
echo ==============================================================================
echo.

echo Stopping Python Backend processes...
powershell -Command "Get-Process | Where-Object {$_.ProcessName -like '*uvicorn*' -or ($_.CommandLine -like '*backend.app:app*')} | Stop-Process -Force -ErrorAction SilentlyContinue"

echo.
echo All Aura AI services stopped cleanly.
echo.
timeout /t 2 /nobreak >nul
