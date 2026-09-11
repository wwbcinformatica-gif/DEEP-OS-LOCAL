@echo off
chcp 65001 >nul 2>&1
title DEEP-OS-LOCAL
color 0A

cd /d "%~dp0"

echo ========================================
echo  DEEP-OS-LOCAL
echo ========================================
echo.

:: Matar processos antigos
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Iniciar backend
echo [1/2] Iniciando backend...
start "Backend" cmd /k "cd /d C:\DEEP-OS-LOCAL\backend && call venv\Scripts\activate && uvicorn main:app --host 127.0.0.1 --port 8000"

:: Esperar backend
timeout /t 6 /nobreak >nul

:: Iniciar frontend
echo [2/2] Iniciando frontend...
start "Frontend" cmd /k "cd /d C:\DEEP-OS-LOCAL\frontend && npx vite --mode development"

:: Abrir navegador
timeout /t 5 /nobreak >nul
start http://127.0.0.1:5175

echo.
echo ========================================
echo  Tudo rodando!
echo ========================================
echo.
echo  Backend:  http://127.0.0.1:8000
echo  Frontend: http://127.0.0.1:5175
echo.
echo  Para fechar: STOP-TOTAL.bat
echo.
pause
