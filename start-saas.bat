@echo off
chcp 65001 >nul 2>&1
title DEEP-OS-LOCAL SaaS
color 0A

cd /d "%~dp0"

echo ============================================
echo   DEEP-OS-LOCAL SaaS
echo ============================================
echo.

:: Matar processos antigos
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Backend
echo [1/3] Iniciando Backend (porta 8001)...
start "Backend" cmd /k "cd /d C:\DEEP-OS-LOCAL\backend && call venv\Scripts\activate && uvicorn main:app --host 127.0.0.1 --port 8001 --reload --reload-dir routes"
timeout /t 5 /nobreak >nul

:: Chatbot
echo [2/3] Iniciando Chatbot Gateway (porta 8010)...
start "Chatbot" cmd /k "cd /d C:\DEEP-OS-LOCAL\chatbot-server && node server.js"
timeout /t 3 /nobreak >nul

:: Frontend SaaS
echo [3/3] Iniciando Frontend SaaS (porta 5176)...
start "Frontend" cmd /k "cd /d C:\DEEP-OS-LOCAL\frontend && npx vite --mode saas --port 5176"
timeout /t 5 /nobreak >nul

:: Abrir navegador
start http://localhost:5176

echo.
echo ============================================
echo   Backend:  http://localhost:8001
echo   Chatbot:  http://localhost:8010
echo   Frontend: http://localhost:5176
echo ============================================
echo.
echo  Para fechar: STOP-TOTAL.bat
echo.
pause
