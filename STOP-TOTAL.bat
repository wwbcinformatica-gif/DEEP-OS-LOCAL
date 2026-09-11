@echo off
chcp 65001 >nul 2>&1
title DEEP-OS - ENCERRANDO SISTEMA
color 0C

echo ===================================================
echo   DEEP-OS - ENCERRANDO SISTEMA
echo ===================================================
echo.

echo [1/4] Finalizando WBC Backend (porta 8001)...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       PID %%a finalizado
)
taskkill /FI "WINDOWTITLE eq WBC Backend*" /F >nul 2>&1
echo       Backend finalizado

echo [2/4] Finalizando DEEP-OS Chatbot (porta 8010)...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8010 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       PID %%a finalizado
)
taskkill /FI "WINDOWTITLE eq DEEP-OS Chatbot*" /F >nul 2>&1
echo       Chatbot finalizado

echo [3/4] Finalizando WBC Frontend / Vite (porta 5176)...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :5176 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       PID %%a finalizado
)
taskkill /FI "WINDOWTITLE eq WBC Frontend*" /F >nul 2>&1
:: Mata qualquer cmd com vite na linha de comando
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq cmd.exe" /V 2^>nul ^| findstr /I "vite"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       CMD vite PID %%a finalizado
)
echo       Frontend finalizado

echo [4/4] Limpando processos restantes (node, python)...
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
echo       OK

echo.
echo ===================================================
echo   Sistema finalizado!
echo ===================================================
echo.
echo   Para reiniciar: start-saas.bat
echo.
pause
