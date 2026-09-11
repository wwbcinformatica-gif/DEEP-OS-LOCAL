@echo off
title DEEP-OS SaaS

cd /d "%~dp0"

echo.
echo Iniciando DEEP-OS SaaS...
echo.

:: Inicia backend
echo [1/3] Iniciando Backend (porta 8001)...
start "WBC Backend" cmd /k "cd /d C:\DEEP-OS\backend && C:\DEEP-OS\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload --reload-dir routes"

:: Aguarda backend iniciar
timeout /t 5 /nobreak >nul

:: Inicia chatbot gateway
echo [2/3] Iniciando Chatbot Gateway (porta 8010)...
start "DEEP-OS Chatbot" cmd /k "cd /d C:\DEEP-OS\chatbot-server && node server.js"

:: Aguarda chatbot iniciar
timeout /t 3 /nobreak >nul

:: Inicia frontend
echo [3/3] Iniciando Frontend SaaS (porta 5176)...
start "WBC Frontend" cmd /k "cd /d C:\DEEP-OS\frontend && npx vite --mode saas --port 5176"

timeout /t 4 /nobreak >nul

echo.
echo ============================================
echo   Backend:    http://localhost:8001
echo   Chatbot:    http://localhost:8010
echo   Frontend:   http://localhost:5176
echo ============================================
echo.
echo Abrindo navegador...
start http://localhost:5176

echo.
echo Pressione QUALQUER TECLA para fechar esta janela...
pause >nul
